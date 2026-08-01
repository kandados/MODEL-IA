from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api as api_module
from src.generation_service import GenerationProgress
from src.models.design_request import DesignRequest, ExplicitDimension
from src.models.mechanical_plan import BoundingBox, MechanicalPlan


def make_design_request() -> DesignRequest:
    return DesignRequest(
        original_request="Caja de 100 x 70 x 30 mm en PETG",
        design_intent="enclosure",
        requested_output=["STEP", "STL", "3MF"],
        identified_objects=[],
        explicit_dimensions_mm=[
            ExplicitDimension(name="width", value_mm=100),
            ExplicitDimension(name="depth", value_mm=70),
            ExplicitDimension(name="height", value_mm=30),
        ],
        explicit_requirements=["Material PETG"],
        web_research_required=False,
        information_to_research=[],
        missing_user_decisions=[],
        interpretation_summary="Caja rectangular parametrizada.",
    )


class FakePipeline:
    def run(
        self,
        user_request: str,
        *,
        requested_formats: list[str],
        output_directory: Path,
        on_progress,
    ) -> SimpleNamespace:
        on_progress(
            GenerationProgress(
                stage="interpret",
                stage_index=0,
                progress=0.1,
                message="Interpretando la petición",
            )
        )
        on_progress(
            GenerationProgress(
                stage="export",
                stage_index=3,
                progress=1.0,
                message="Archivos preparados",
            )
        )

        output_directory.mkdir(parents=True, exist_ok=True)
        exported_files = {}

        for export_name, file_name, format_name in (
            ("assembly", "enclosure.step", "step"),
            ("base", "enclosure_base.stl", "stl"),
            ("lid", "enclosure_lid.stl", "stl"),
            (
                "print_layout",
                "enclosure_print_layout.3mf",
                "3mf",
            ),
        ):
            path = output_directory / file_name
            path.write_bytes(b"model-ia-test")
            exported_files[export_name] = SimpleNamespace(
                files=[
                    SimpleNamespace(
                        format=format_name,
                        path=path,
                    )
                ]
            )

        return SimpleNamespace(
            design_request=make_design_request(),
            mechanical_plan=MechanicalPlan(
                external_bounding_box=BoundingBox(
                    width_mm=100,
                    depth_mm=70,
                    height_mm=30,
                )
            ),
            cad_result=SimpleNamespace(
                exports=exported_files,
                validation=SimpleNamespace(warnings=[]),
            ),
        )


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_generations_root = api_module.GENERATIONS_ROOT
        api_module.GENERATIONS_ROOT = Path(self.temporary_directory.name)

        with api_module._jobs_lock:
            api_module._jobs.clear()

        self.client = TestClient(api_module.app)

    def tearDown(self) -> None:
        self.client.close()
        api_module.GENERATIONS_ROOT = self.original_generations_root

        with api_module._jobs_lock:
            api_module._jobs.clear()

        self.temporary_directory.cleanup()

    def test_health_generation_websocket_and_download_contract(self) -> None:
        health_response = self.client.get("/api/v1/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")

        with patch.object(api_module, "GenerationPipeline", FakePipeline):
            response = self.client.post(
                "/api/v1/generations",
                json={
                    "project_id": "test-project",
                    "message": "Caja de 100 x 70 x 30 mm en PETG",
                    "attachment_names": [],
                    "requested_formats": ["STEP", "STL", "3MF"],
                },
            )

        self.assertEqual(response.status_code, 202)
        accepted = response.json()
        generation_id = accepted["generation_id"]

        with self.client.websocket_connect(
            accepted["websocket_url"]
        ) as websocket:
            first_event = websocket.receive_json()
            second_event = websocket.receive_json()
            completed_event = websocket.receive_json()

        self.assertEqual(first_event["type"], "progress")
        self.assertEqual(second_event["stage"], "export")
        self.assertEqual(completed_event["type"], "completed")

        result = completed_event["result"]
        self.assertEqual(result["project_id"], "test-project")
        self.assertEqual(result["specification"]["material"], "PETG")
        self.assertEqual(len(result["artifacts"]), 3)
        self.assertEqual(result["preview"]["format"], "STL")
        self.assertEqual(len(result["preview"]["parts"]), 2)
        self.assertEqual(
            result["preview"]["parts"][0]["id"],
            "base",
        )
        self.assertEqual(
            result["preview"]["parts"][1]["id"],
            "lid",
        )
        self.assertEqual(
            result["preview"]["parts"][1]["assembled_position_mm"],
            [0.0, 0.0, 18.0],
        )

        stl_artifact = next(
            artifact
            for artifact in result["artifacts"]
            if artifact["format"] == "STL"
        )
        self.assertEqual(len(stl_artifact["files"]), 2)

        for stl_file in stl_artifact["files"]:
            file_response = self.client.get(stl_file["download_url"])
            self.assertEqual(file_response.status_code, 200)
            self.assertEqual(file_response.content, b"model-ia-test")

        invalid_response = self.client.get(
            "/api/v1/generations/../files/enclosure.stl"
        )
        self.assertEqual(invalid_response.status_code, 404)
        self.assertTrue(generation_id.startswith("gen_"))


if __name__ == "__main__":
    unittest.main()
