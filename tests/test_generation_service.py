from __future__ import annotations

import tempfile
import unittest
import zipfile
from xml.etree import ElementTree
from pathlib import Path
from types import SimpleNamespace

from src.cad.cad_generator import CADGenerator
from src.generation_service import (
    GenerationPipeline,
    determine_material,
    determine_tolerance_mm,
    normalize_formats,
)
from src.models.design_request import DesignRequest, ExplicitDimension
from src.models.engineering_knowledge import (
    Component,
    Dimensions,
    EngineeringKnowledge,
    Identity,
)
from src.models.mechanical_plan import BoundingBox, MechanicalPlan
from src.planner.mechanical_planner import MechanicalPlanner


def make_design_request() -> DesignRequest:
    return DesignRequest(
        original_request=(
            "Caja de 100 x 70 x 30 mm en PETG con tolerancia de 0,4 mm"
        ),
        design_intent="enclosure",
        requested_output=["STEP", "STL", "3MF"],
        identified_objects=[],
        explicit_dimensions_mm=[
            ExplicitDimension(name="width", value_mm=100),
            ExplicitDimension(name="depth", value_mm=70),
            ExplicitDimension(name="height", value_mm=30),
        ],
        explicit_requirements=[
            "Material PETG",
            "Tolerancia de 0,4 mm",
        ],
        web_research_required=False,
        information_to_research=[],
        missing_user_decisions=[],
        interpretation_summary="Caja rectangular parametrizada.",
    )


class FakeDesignAgent:
    def __init__(self, result: DesignRequest) -> None:
        self.result = result

    def interpret(self, user_request: str) -> DesignRequest:
        return self.result


class FakeKnowledgeBuilder:
    def build(self, **_: object) -> EngineeringKnowledge:
        return EngineeringKnowledge(
            identity=Identity(aliases=["enclosure"]),
            dimensions=Dimensions(
                width_mm=96,
                depth_mm=66,
                height_mm=26,
            ),
        )


class FakeMechanicalPlanner:
    def build(self, _: EngineeringKnowledge) -> MechanicalPlan:
        return MechanicalPlan(
            external_bounding_box=BoundingBox(
                width_mm=100,
                depth_mm=70,
                height_mm=30,
            )
        )


class FakeCADGenerator:
    def __init__(self) -> None:
        self.output_directory: Path | None = None
        self.formats: tuple[str, ...] = ()

    def generate_and_export(
        self,
        plan: MechanicalPlan,
        file_name: str,
        *,
        formats: tuple[str, ...],
        output_directory: str | Path,
    ) -> SimpleNamespace:
        self.output_directory = Path(output_directory)
        self.formats = formats
        return SimpleNamespace(
            validation=SimpleNamespace(
                is_valid=True,
                warnings=[],
            ),
            exports={},
        )


class GenerationServiceTests(unittest.TestCase):
    def test_cad_exports_base_and_lid_as_real_multipart_outputs(
        self,
    ) -> None:
        plan = MechanicalPlan(
            external_bounding_box=BoundingBox(
                width_mm=100,
                depth_mm=70,
                height_mm=30,
            ),
            validation_rules=["wall_thickness=2"],
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = CADGenerator().generate_and_export(
                plan,
                file_name="multipart_test",
                formats=("step", "stl", "3mf"),
                output_directory=temporary_directory,
            )

            self.assertEqual(result.assembly.solids().size(), 2)
            self.assertEqual(result.print_layout.solids().size(), 2)
            self.assertEqual(
                set(result.exports or {}),
                {"assembly", "base", "lid", "print_layout"},
            )

            step_path = Path(temporary_directory) / "multipart_test.step"
            step_text = step_path.read_text(errors="ignore").lower()
            self.assertIn("base", step_text)
            self.assertIn("lid", step_text)

            layout_path = (
                Path(temporary_directory)
                / "multipart_test_print_layout.3mf"
            )
            with zipfile.ZipFile(layout_path) as archive:
                model_xml = archive.read("3D/3dmodel.model")

            root = ElementTree.fromstring(model_xml)
            namespace = {
                "m": (
                    "http://schemas.microsoft.com/"
                    "3dmanufacturing/core/2015/02"
                )
            }
            x_bounds = []

            for object_node in root.findall(".//m:object", namespace):
                vertices = object_node.findall(".//m:vertex", namespace)
                if not vertices:
                    continue
                x_coordinates = [
                    float(vertex.attrib["x"])
                    for vertex in vertices
                ]
                x_bounds.append(
                    (min(x_coordinates), max(x_coordinates))
                )

            x_bounds.sort()
            self.assertEqual(len(x_bounds), 2)
            self.assertGreaterEqual(
                x_bounds[1][0] - x_bounds[0][1],
                5.0,
            )

    def test_explicit_part_dimensions_are_not_inflated(self) -> None:
        knowledge = EngineeringKnowledge(
            identity=Identity(aliases=["enclosure"]),
            dimensions=Dimensions(
                width_mm=100,
                depth_mm=70,
                height_mm=30,
            ),
        )

        plan = MechanicalPlanner().build(knowledge)

        self.assertEqual(
            plan.external_bounding_box,
            BoundingBox(
                width_mm=100,
                depth_mm=70,
                height_mm=30,
            ),
        )

    def test_enclosed_component_keeps_engineering_margin(self) -> None:
        knowledge = EngineeringKnowledge(
            identity=Identity(aliases=["PCB"]),
            dimensions=Dimensions(
                width_mm=96,
                depth_mm=66,
                height_mm=26,
            ),
            components=[
                Component(
                    id="pcb",
                    type="pcb",
                    name="PCB",
                )
            ],
        )

        plan = MechanicalPlanner().build(knowledge)

        self.assertEqual(
            plan.external_bounding_box,
            BoundingBox(
                width_mm=100,
                depth_mm=70,
                height_mm=30,
            ),
        )

    def test_pipeline_reuses_components_and_emits_all_visual_stages(
        self,
    ) -> None:
        design_request = make_design_request()
        cad_generator = FakeCADGenerator()
        progress_events = []
        pipeline = GenerationPipeline(
            design_agent=FakeDesignAgent(design_request),
            knowledge_builder=FakeKnowledgeBuilder(),
            mechanical_planner=FakeMechanicalPlanner(),
            cad_generator=cad_generator,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = pipeline.run(
                design_request.original_request,
                requested_formats=["STL", "STEP", "STL", "3MF"],
                output_directory=temporary_directory,
                on_progress=progress_events.append,
            )

        self.assertEqual(result.file_name, "enclosure")
        self.assertEqual(result.formats, ("stl", "step", "3mf"))
        self.assertEqual(
            {event.stage_index for event in progress_events},
            {0, 1, 2, 3},
        )
        self.assertEqual(
            cad_generator.output_directory,
            Path(temporary_directory),
        )

    def test_material_tolerance_and_formats_are_normalized(self) -> None:
        design_request = make_design_request()

        self.assertEqual(determine_material(design_request), "PETG")
        self.assertEqual(determine_tolerance_mm(design_request), 0.4)
        self.assertEqual(
            normalize_formats([".STL", "step", "STL", "desconocido"]),
            ("stl", "step"),
        )


if __name__ == "__main__":
    unittest.main()
