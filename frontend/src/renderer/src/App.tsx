import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas, useThree } from "@react-three/fiber";
import {
  Edges,
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
  RoundedBox,
} from "@react-three/drei";
import {
  Box as BoxIcon,
  Check,
  ChevronDown,
  ChevronUp,
  CircleCheck,
  Folder,
  FolderOpen,
  Home,
  Layers3,
  Maximize2,
  Move3d,
  Paperclip,
  Pencil,
  Plus,
  RotateCw,
  Ruler,
  Send,
  Settings,
  Sparkles,
  Trash2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Box3, type BufferGeometry, Vector3 } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import {
  AdaptiveModelIAClient,
  PIPELINE_STAGES,
  type ClientConnection,
  type ExportArtifact,
  type GenerationResult,
  type ModelPreview,
  type PipelineProgressEvent,
} from "./model-ia-client";
import {
  createInitialWorkspace,
  createWorkspaceProject,
  type ConversationMessage,
  type WorkspaceAttachment,
  type WorkspaceProject,
  workspaceStore,
} from "./workspace-store";

interface CameraRigProps {
  distance: number;
  resetVersion: number;
}

function CameraRig({
  distance,
  resetVersion,
}: CameraRigProps): null {
  const { camera } = useThree();

  useEffect(() => {
    camera.position.copy(
      new Vector3(8.2, 6.5, 9.4).multiplyScalar(distance),
    );
    camera.lookAt(0, 0.2, 0);
    camera.updateProjectionMatrix();
  }, [camera, distance, resetVersion]);

  return null;
}

interface EnclosureAssemblyProps {
  exploded: boolean;
}

function EnclosureAssembly({
  exploded,
}: EnclosureAssemblyProps): React.JSX.Element {
  const ventPositions = useMemo(
    () =>
      Array.from({ length: 28 }, (_, index) => {
        const row = Math.floor(index / 7);
        const column = index % 7;

        return {
          x: -1.65 + column * 0.55,
          z: -0.78 + row * 0.52,
        };
      }),
    [],
  );

  const standoffPositions = [
    [-2.35, -1.6],
    [2.35, -1.6],
    [-2.35, 1.6],
    [2.35, 1.6],
  ] as const;

  const screwPositions = [
    [-2.65, -1.85],
    [2.65, -1.85],
    [-2.65, 1.85],
    [2.65, 1.85],
  ] as const;

  const baseY = exploded ? -1.15 : -0.65;
  const lidY = exploded ? 2.15 : 0.55;

  return (
    <group rotation={[0, -0.18, 0]}>
      <group position={[0, baseY, 0]}>
        <RoundedBox
          args={[6.7, 0.3, 5]}
          radius={0.28}
          smoothness={6}
          position={[0, -0.58, 0]}
          castShadow
          receiveShadow
        >
          <meshStandardMaterial
            color="#667785"
            metalness={0.38}
            roughness={0.42}
          />
          <Edges
            threshold={18}
            color="#73e4fb"
          />
        </RoundedBox>

        <RoundedBox
          args={[6.2, 0.16, 4.5]}
          radius={0.18}
          smoothness={4}
          position={[0, -0.36, 0]}
          receiveShadow
        >
          <meshStandardMaterial
            color="#2b3b46"
            metalness={0.18}
            roughness={0.62}
          />
        </RoundedBox>

        <RoundedBox
          args={[0.3, 1.35, 4.65]}
          radius={0.13}
          smoothness={4}
          position={[-3.12, 0, 0]}
          castShadow
        >
          <meshStandardMaterial
            color="#60717e"
            metalness={0.36}
            roughness={0.44}
          />
          <Edges
            threshold={18}
            color="#62d8f1"
          />
        </RoundedBox>
        <RoundedBox
          args={[0.3, 1.35, 4.65]}
          radius={0.13}
          smoothness={4}
          position={[3.12, 0, 0]}
          castShadow
        >
          <meshStandardMaterial
            color="#60717e"
            metalness={0.36}
            roughness={0.44}
          />
          <Edges
            threshold={18}
            color="#62d8f1"
          />
        </RoundedBox>
        <RoundedBox
          args={[6.05, 1.35, 0.3]}
          radius={0.13}
          smoothness={4}
          position={[0, 0, -2.34]}
          castShadow
        >
          <meshStandardMaterial
            color="#60717e"
            metalness={0.36}
            roughness={0.44}
          />
          <Edges
            threshold={18}
            color="#62d8f1"
          />
        </RoundedBox>
        <RoundedBox
          args={[6.05, 1.35, 0.3]}
          radius={0.13}
          smoothness={4}
          position={[0, 0, 2.34]}
          castShadow
        >
          <meshStandardMaterial
            color="#60717e"
            metalness={0.36}
            roughness={0.44}
          />
          <Edges
            threshold={18}
            color="#62d8f1"
          />
        </RoundedBox>

        <RoundedBox
          args={[4.55, 0.16, 3.25]}
          radius={0.12}
          smoothness={4}
          position={[-0.2, -0.18, -0.05]}
          castShadow
        >
          <meshStandardMaterial
            color="#236875"
            metalness={0.16}
            roughness={0.52}
          />
          <Edges
            threshold={15}
            color="#69deea"
          />
        </RoundedBox>

        {standoffPositions.map(([x, z]) => (
          <group
            key={`${x}-${z}`}
            position={[x, 0.05, z]}
          >
            <mesh castShadow>
              <cylinderGeometry args={[0.24, 0.29, 0.95, 32]} />
              <meshStandardMaterial
                color="#82919b"
                metalness={0.42}
                roughness={0.38}
              />
            </mesh>
            <mesh position={[0, 0.49, 0]}>
              <cylinderGeometry args={[0.1, 0.1, 0.05, 24]} />
              <meshStandardMaterial color="#0a1015" />
            </mesh>
          </group>
        ))}

        <RoundedBox
          args={[0.85, 0.4, 0.13]}
          radius={0.09}
          smoothness={4}
          position={[1.62, -0.05, 2.51]}
        >
          <meshStandardMaterial color="#03070a" />
        </RoundedBox>
        <RoundedBox
          args={[0.5, 0.3, 0.13]}
          radius={0.04}
          smoothness={4}
          position={[0.55, -0.05, 2.51]}
        >
          <meshStandardMaterial color="#03070a" />
        </RoundedBox>
        <RoundedBox
          args={[0.42, 0.28, 0.13]}
          radius={0.04}
          smoothness={4}
          position={[-0.34, -0.05, 2.51]}
        >
          <meshStandardMaterial color="#03070a" />
        </RoundedBox>
      </group>

      <group position={[0, lidY, 0]}>
        <RoundedBox
          args={[6.65, 0.44, 4.95]}
          radius={0.3}
          smoothness={7}
          castShadow
        >
          <meshStandardMaterial
            color="#728391"
            metalness={0.4}
            roughness={0.4}
          />
          <Edges
            threshold={16}
            color="#82e9fc"
          />
        </RoundedBox>

        {ventPositions.map(({ x, z }) => (
          <RoundedBox
            key={`${x}-${z}`}
            args={[0.38, 0.08, 0.12]}
            radius={0.045}
            smoothness={3}
            position={[x, 0.255, z]}
          >
            <meshStandardMaterial color="#070c11" />
          </RoundedBox>
        ))}

        {screwPositions.map(([x, z]) => (
          <group
            key={`${x}-${z}`}
            position={[x, 0.25, z]}
          >
            <mesh>
              <cylinderGeometry args={[0.18, 0.18, 0.08, 32]} />
              <meshStandardMaterial color="#080d11" />
            </mesh>
            <mesh position={[0, 0.046, 0]}>
              <torusGeometry args={[0.19, 0.026, 12, 32]} />
              <meshStandardMaterial
                color="#a1adb5"
                metalness={0.5}
                roughness={0.34}
              />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  );
}

interface ModelAssemblyProps {
  exploded: boolean;
  preview?: ModelPreview;
}

function ModelAssembly({
  exploded,
  preview,
}: ModelAssemblyProps): React.JSX.Element {
  const [loadedParts, setLoadedParts] = useState<
    Array<{
      id: string;
      label: string;
      geometry: BufferGeometry;
      assembledPositionMm: [number, number, number];
      explodedPositionMm: [number, number, number];
    }>
  >([]);

  useEffect(() => {
    let cancelled = false;
    const geometries: BufferGeometry[] = [];
    const sourceParts =
      preview?.parts && preview.parts.length > 0
        ? preview.parts
        : preview?.url
          ? [
              {
                id: "model",
                label: "Modelo",
                url: preview.url,
                assembledPositionMm: [0, 0, 0] as [number, number, number],
                explodedPositionMm: [0, 0, 0] as [number, number, number],
              },
            ]
          : [];

    setLoadedParts([]);

    if (sourceParts.length === 0) {
      return undefined;
    }

    const loader = new STLLoader();

    void Promise.all(
      sourceParts.map(async (part) => {
        const candidate = await loader.loadAsync(part.url);
        geometries.push(candidate);

        if (cancelled) {
          candidate.dispose();
          return null;
        }

        candidate.computeVertexNormals();
        candidate.computeBoundingBox();

        return {
          id: part.id,
          label: part.label,
          geometry: candidate,
          assembledPositionMm: part.assembledPositionMm,
          explodedPositionMm: part.explodedPositionMm,
        };
      }),
    )
      .then((parts) => {
        if (!cancelled) {
          setLoadedParts(
            parts.filter((part) => part !== null),
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadedParts([]);
        }
      });

    return () => {
      cancelled = true;
      geometries.forEach((geometry) => geometry.dispose());
    };
  }, [preview]);

  const layout = useMemo(() => {
    if (loadedParts.length === 0) {
      return null;
    }

    const bounds = new Box3();
    bounds.makeEmpty();

    const parts = loadedParts.map((part) => {
      const positionMm = exploded
        ? part.explodedPositionMm
        : part.assembledPositionMm;
      const position = new Vector3(...positionMm);
      const partBounds = part.geometry.boundingBox?.clone();

      if (partBounds) {
        partBounds.translate(position);
        bounds.union(partBounds);
      }

      return { ...part, position };
    });

    if (bounds.isEmpty()) {
      return null;
    }

    const size = bounds.getSize(new Vector3());
    const center = bounds.getCenter(new Vector3());
    const largestDimension = Math.max(size.x, size.y, size.z);

    return {
      parts,
      center,
      scale: largestDimension > 0 ? 7 / largestDimension : 1,
    };
  }, [exploded, loadedParts]);

  if (!layout) {
    return <EnclosureAssembly exploded={exploded} />;
  }

  return (
    <group
      rotation={[-Math.PI / 2, 0, 0]}
      scale={layout.scale}
    >
      {layout.parts.map((part, index) => (
        <mesh
          key={part.id}
          geometry={part.geometry}
          position={[
            part.position.x - layout.center.x,
            part.position.y - layout.center.y,
            part.position.z - layout.center.z,
          ]}
          castShadow
          receiveShadow
          name={part.label}
        >
          <meshStandardMaterial
            color={index === 0 ? "#718491" : "#8aa5b2"}
            metalness={0.28}
            roughness={0.48}
          />
          <Edges
            threshold={20}
            color="#74e3f8"
          />
        </mesh>
      ))}
    </group>
  );
}

interface ViewerSceneProps {
  autoRotate: boolean;
  exploded: boolean;
  distance: number;
  resetVersion: number;
  preview?: ModelPreview;
}

function ViewerScene({
  autoRotate,
  exploded,
  distance,
  resetVersion,
  preview,
}: ViewerSceneProps): React.JSX.Element {
  return (
    <Canvas
      camera={{
        position: [8.2, 6.5, 9.4],
        fov: 34,
        near: 0.1,
        far: 120,
      }}
      dpr={[1, 2]}
      gl={{
        antialias: true,
        alpha: true,
      }}
      shadows
    >
      <color
        attach="background"
        args={["#09131c"]}
      />
      <fog
        attach="fog"
        args={["#09131c", 16, 38]}
      />
      <ambientLight intensity={1.25} />
      <hemisphereLight
        intensity={1.7}
        color="#e9fbff"
        groundColor="#142631"
      />
      <directionalLight
        position={[5, 10, 6]}
        intensity={4.2}
        color="#f1fcff"
        castShadow
      />
      <directionalLight
        position={[-6, 3, 7]}
        intensity={2.4}
        color="#b9eaff"
      />
      <spotLight
        position={[-7, 5, -3]}
        intensity={32}
        color="#36d8f5"
        angle={0.45}
        penumbra={0.9}
      />

      <CameraRig
        distance={distance}
        resetVersion={resetVersion}
      />
      <ModelAssembly
        exploded={exploded}
        preview={preview}
      />

      <Grid
        args={[26, 26]}
        position={[0, -2.35, 0]}
        cellSize={0.45}
        cellThickness={0.45}
        cellColor="#21313d"
        sectionSize={2.7}
        sectionThickness={0.8}
        sectionColor="#2b4555"
        fadeDistance={23}
        fadeStrength={1.5}
        infiniteGrid
      />

      <OrbitControls
        makeDefault
        target={[0, 0, 0]}
        enableDamping
        dampingFactor={0.08}
        minDistance={7}
        maxDistance={28}
        autoRotate={autoRotate}
        autoRotateSpeed={0.75}
      />

      <GizmoHelper
        alignment="top-right"
        margin={[64, 68]}
      >
        <GizmoViewport
          axisColors={["#ff6470", "#63d47a", "#3bc8ff"]}
          labelColor="#e8f2f7"
        />
      </GizmoHelper>
    </Canvas>
  );
}

function BrandMark(): React.JSX.Element {
  return (
    <svg
      className="brand-mark"
      viewBox="0 0 48 48"
      role="img"
      aria-label="Model-IA"
    >
      <path
        d="M24 3 41 13v20L24 43 7 33V13Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="m24 8 12.5 7.2v14.5L24 37 11.5 29.7V15.2Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        opacity=".72"
      />
      <path
        d="m24 8 3.6 13.3L41 13M27.6 21.3 36.5 29.7M27.6 21.3 24 37M27.6 21.3 11.5 29.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        opacity=".55"
      />
    </svg>
  );
}

interface SidebarProps {
  projects: WorkspaceProject[];
  activeProjectId: string;
  managementDisabled: boolean;
  onCreateProject: () => void;
  onDeleteProject: (projectId: string) => Promise<void>;
  onRenameProject: (projectId: string, name: string) => void;
  onSelectProject: (projectId: string) => void;
}

const formatProjectAge = (timestamp: string): string => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "Guardado";
  }

  const elapsedMs = Date.now() - date.getTime();
  if (elapsedMs < 5 * 60_000) {
    return "Ahora";
  }
  if (elapsedMs < 24 * 60 * 60_000) {
    return "Hoy";
  }
  if (elapsedMs < 48 * 60 * 60_000) {
    return "Ayer";
  }

  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
  }).format(date);
};

function Sidebar({
  projects,
  activeProjectId,
  managementDisabled,
  onCreateProject,
  onDeleteProject,
  onRenameProject,
  onSelectProject,
}: SidebarProps): React.JSX.Element {
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const beginRename = (project: WorkspaceProject): void => {
    setEditingProjectId(project.id);
    setEditingName(project.name);
  };

  const cancelRename = (): void => {
    setEditingProjectId(null);
    setEditingName("");
  };

  const commitRename = (): void => {
    if (!editingProjectId) {
      return;
    }

    const name = editingName.trim();
    if (name) {
      onRenameProject(editingProjectId, name);
    }
    cancelRename();
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-drag-region" />
      <div className="brand">
        <BrandMark />
        <span>MODEL-IA</span>
      </div>

      <div className="sidebar-heading">Proyectos</div>

      <button
        className="new-project-button"
        type="button"
        disabled={managementDisabled}
        onClick={onCreateProject}
      >
        <Plus size={21} />
        Nuevo proyecto
      </button>

      <nav
        className="project-list"
        aria-label="Proyectos"
      >
        {projects.map((project) => {
          const isActive = project.id === activeProjectId;
          const isEditing = project.id === editingProjectId;

          return (
            <div
              className={`project-item${isActive ? " active" : ""}`}
              key={project.id}
            >
              <button
                className="project-select"
                type="button"
                onClick={() => onSelectProject(project.id)}
              >
                {isActive ? (
                  <FolderOpen size={23} />
                ) : (
                  <Folder size={23} />
                )}
                {isEditing ? (
                  <input
                    autoFocus
                    maxLength={80}
                    value={editingName}
                    aria-label="Nombre del proyecto"
                    onBlur={commitRename}
                    onChange={(event) => setEditingName(event.target.value)}
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        commitRename();
                      } else if (event.key === "Escape") {
                        event.preventDefault();
                        cancelRename();
                      }
                    }}
                  />
                ) : (
                  <span className="project-copy">
                    <strong>{project.name}</strong>
                    <small>{formatProjectAge(project.updatedAt)}</small>
                  </span>
                )}
              </button>

              {!isEditing && (
                <span className="project-actions">
                  <button
                    type="button"
                    disabled={managementDisabled}
                    aria-label={`Renombrar ${project.name}`}
                    title="Renombrar proyecto"
                    onClick={() => beginRename(project)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="delete-project-button"
                    type="button"
                    disabled={managementDisabled}
                    aria-label={`Eliminar ${project.name}`}
                    title="Eliminar proyecto"
                    onClick={() => void onDeleteProject(project.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </span>
              )}
            </div>
          );
        })}
      </nav>

      <button
        className="settings-button"
        type="button"
        aria-label="Ajustes"
        title="Ajustes"
      >
        <Settings size={22} />
      </button>
    </aside>
  );
}

interface PipelineProps {
  completedStage: number;
  currentStage: number;
  isGenerating: boolean;
}

function Pipeline({
  completedStage,
  currentStage,
  isGenerating,
}: PipelineProps): React.JSX.Element {
  return (
    <div
      className="pipeline"
      aria-label="Progreso del pipeline"
    >
      {PIPELINE_STAGES.map((stage, index) => {
        const completed = index <= completedStage;
        const current = isGenerating && index === currentStage;

        return (
          <div
            className={`pipeline-step${completed ? " completed" : ""}${
              current ? " current" : ""
            }`}
            key={stage.id}
          >
            <div className="pipeline-node">
              {completed ? <Check size={17} /> : <span />}
            </div>
            <span>{stage.label}</span>
          </div>
        );
      })}
    </div>
  );
}

interface ViewerToolbarProps {
  autoRotate: boolean;
  exploded: boolean;
  onReset: () => void;
  onToggleRotate: () => void;
  onToggleExploded: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFullscreen: () => void;
}

function ViewerToolbar({
  autoRotate,
  exploded,
  onReset,
  onToggleRotate,
  onToggleExploded,
  onZoomIn,
  onZoomOut,
  onFullscreen,
}: ViewerToolbarProps): React.JSX.Element {
  return (
    <div
      className="viewer-toolbar"
      aria-label="Controles de vista"
    >
      <button
        type="button"
        onClick={onReset}
        title="Restablecer vista"
      >
        <Home size={20} />
      </button>
      <button
        className={autoRotate ? "active" : ""}
        type="button"
        onClick={onToggleRotate}
        title="Rotación automática"
      >
        <RotateCw size={20} />
      </button>
      <button
        className={exploded ? "active" : ""}
        type="button"
        onClick={onToggleExploded}
        title="Vista explosionada"
      >
        <Move3d size={20} />
      </button>
      <span className="toolbar-separator" />
      <button
        type="button"
        onClick={onZoomIn}
        title="Acercar"
      >
        <ZoomIn size={20} />
      </button>
      <button
        type="button"
        onClick={onZoomOut}
        title="Alejar"
      >
        <ZoomOut size={20} />
      </button>
      <button
        type="button"
        onClick={onFullscreen}
        title="Pantalla completa"
      >
        <Maximize2 size={20} />
      </button>
    </div>
  );
}

interface InspectorProps {
  result: GenerationResult;
  onExport: (format: "STEP" | "STL" | "3MF") => Promise<void>;
}

function Inspector({
  result,
  onExport,
}: InspectorProps): React.JSX.Element {
  const [specificationsOpen, setSpecificationsOpen] = useState(true);
  const [validationOpen, setValidationOpen] = useState(true);
  const { dimensions } = result.specification;

  return (
    <aside className="inspector">
      <section className="inspector-card">
        <button
          className="inspector-card-title"
          type="button"
          onClick={() => setSpecificationsOpen((value) => !value)}
        >
          <span>Especificaciones</span>
          {specificationsOpen ? (
            <ChevronUp size={18} />
          ) : (
            <ChevronDown size={18} />
          )}
        </button>

        {specificationsOpen && (
          <div className="inspector-card-content">
            <div className="property-row">
              <span className="property-icon">
                <Ruler size={25} />
              </span>
              <span>
                <small>Dimensiones</small>
                <strong>
                  {dimensions.widthMm} × {dimensions.depthMm} ×{" "}
                  {dimensions.heightMm} mm
                </strong>
              </span>
            </div>
            <div className="property-row">
              <span className="property-icon">
                <Layers3 size={25} />
              </span>
              <span>
                <small>Material</small>
                <strong>{result.specification.material}</strong>
              </span>
            </div>
            <div className="property-row">
              <span className="property-icon">
                <BoxIcon size={25} />
              </span>
              <span>
                <small>Tolerancia</small>
                <strong>
                  {result.specification.toleranceMm
                    .toFixed(1)
                    .replace(".", ",")}{" "}
                  mm
                </strong>
              </span>
            </div>
          </div>
        )}
      </section>

      <section className="inspector-card">
        <button
          className="inspector-card-title"
          type="button"
          onClick={() => setValidationOpen((value) => !value)}
        >
          <span>Validación</span>
          {validationOpen ? (
            <ChevronUp size={18} />
          ) : (
            <ChevronDown size={18} />
          )}
        </button>

        {validationOpen && (
          <div className="validation-list">
            {result.validations.map((validation) => (
              <div
                className={`validation-row ${validation.status}`}
                key={validation.id}
              >
                <span className="validation-icon">
                  <CircleCheck size={26} />
                </span>
                <span>{validation.label}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="export-card">
        {result.artifacts.map((artifact) => (
          <button
            key={artifact.format}
            type="button"
            disabled={!artifact.available}
            onClick={() => void onExport(artifact.format)}
            title={
              artifact.files?.map((file) => file.fileName).join(" + ") ??
              artifact.fileName
            }
          >
            {artifact.format}
          </button>
        ))}
      </section>
    </aside>
  );
}

interface ComposerProps {
  value: string;
  attachments: WorkspaceAttachment[];
  conversation: ConversationMessage[];
  notice: string;
  isGenerating: boolean;
  onChange: (value: string) => void;
  onAttach: () => Promise<void>;
  onOpenAttachment: (attachment: WorkspaceAttachment) => Promise<void>;
  onRemoveAttachment: (attachment: WorkspaceAttachment) => Promise<void>;
  onSubmit: () => void;
}

function Composer({
  value,
  attachments,
  conversation,
  notice,
  isGenerating,
  onChange,
  onAttach,
  onOpenAttachment,
  onRemoveAttachment,
  onSubmit,
}: ComposerProps): React.JSX.Element {
  const conversationEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ block: "end" });
  }, [conversation]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <section className="composer-panel">
      <div className="assistant-orb">
        <Sparkles size={22} />
      </div>

      <div className="composer-content">
        <div
          className="conversation-log"
          aria-label="Historial de conversación"
        >
          {conversation.map((entry) => (
            <article
              className={`conversation-message ${entry.role}`}
              key={entry.id}
            >
              <span>{entry.role === "user" ? "Tú" : "Model-IA"}</span>
              <p>{entry.content}</p>
              {entry.attachmentNames.length > 0 && (
                <small>
                  <Paperclip size={11} />
                  {entry.attachmentNames.join(", ")}
                </small>
              )}
            </article>
          ))}
          <div ref={conversationEndRef} />
        </div>

        <form
          className="composer"
          onSubmit={handleSubmit}
        >
          <textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Describe un cambio o adjunta un croquis..."
            aria-label="Mensaje para Model-IA"
          />

          {attachments.length > 0 && (
            <div className="attachment-list">
              {attachments.map((attachment) => (
                <span
                  className="attachment-chip"
                  key={attachment.id}
                >
                  <Paperclip size={13} />
                  <button
                    className="attachment-name"
                    type="button"
                    title={`Abrir ${attachment.name}`}
                    onClick={() => void onOpenAttachment(attachment)}
                  >
                    {attachment.name}
                  </button>
                  <button
                    type="button"
                    aria-label={`Eliminar ${attachment.name}`}
                    onClick={() => void onRemoveAttachment(attachment)}
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="composer-actions">
            <button
              className="attach-button"
              type="button"
              disabled={isGenerating}
              onClick={() => void onAttach()}
            >
              <Paperclip size={19} />
              Adjuntar
            </button>
            <span
              className="composer-notice"
              aria-live="polite"
            >
              {notice}
            </span>
            <button
              className="send-button"
              type="submit"
              disabled={isGenerating}
            >
              <Send size={18} />
              {isGenerating ? "Procesando" : "Enviar"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

const createConversationEntry = (
  role: ConversationMessage["role"],
  content: string,
  attachmentNames: string[] = [],
): ConversationMessage => ({
  id: crypto.randomUUID(),
  role,
  content,
  createdAt: new Date().toISOString(),
  attachmentNames,
});

const deriveProjectName = (prompt: string): string => {
  const normalized = prompt
    .replace(/^(diseña|genera|crea|quiero|necesito)\s+/i, "")
    .replace(/[.!?]+$/, "")
    .trim();
  const candidate = normalized || "Nuevo diseño";
  const shortened =
    candidate.length > 42 ? `${candidate.slice(0, 39).trim()}...` : candidate;

  return shortened.charAt(0).toUpperCase() + shortened.slice(1);
};

export default function App(): React.JSX.Element {
  const [workspace, setWorkspace] = useState(createInitialWorkspace);
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [connection, setConnection] = useState<ClientConnection>({
    mode: "checking",
    label: "Comprobando backend",
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [exploded, setExploded] = useState(true);
  const [cameraDistance, setCameraDistance] = useState(1);
  const [resetVersion, setResetVersion] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const viewerRef = useRef<HTMLElement>(null);
  const client = useMemo(
    () => new AdaptiveModelIAClient(setConnection),
    [],
  );

  const { projects, activeProjectId } = workspace;
  const activeProject =
    projects.find((project) => project.id === activeProjectId) ??
    projects[0]!;

  const updateProject = useCallback(
    (
      projectId: string,
      updater: (project: WorkspaceProject) => WorkspaceProject,
      touch = false,
    ): void => {
      setWorkspace((current) => ({
        ...current,
        projects: current.projects.map((project) => {
          if (project.id !== projectId) {
            return project;
          }

          const updatedProject = updater(project);
          return touch
            ? {
                ...updatedProject,
                updatedAt: new Date().toISOString(),
              }
            : updatedProject;
        }),
      }));
    },
    [],
  );

  const setProjectNotice = useCallback(
    (projectId: string, notice: string): void => {
      updateProject(
        projectId,
        (project) => ({ ...project, notice }),
      );
    },
    [updateProject],
  );

  useEffect(
    () => () => {
      abortControllerRef.current?.abort();
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;

    void workspaceStore
      .load()
      .then((storedWorkspace) => {
        if (!cancelled) {
          setWorkspace(storedWorkspace);
          setStorageError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setStorageError(
            error instanceof Error
              ? `No se pudieron recuperar los proyectos: ${error.message}`
              : "No se pudieron recuperar los proyectos",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setWorkspaceReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!workspaceReady) {
      return undefined;
    }

    const saveTimer = window.setTimeout(() => {
      void workspaceStore
        .save(workspace)
        .then(() => setStorageError(null))
        .catch((error: unknown) => {
          setStorageError(
            error instanceof Error
              ? `No se pudo guardar: ${error.message}`
              : "No se pudieron guardar los cambios",
          );
        });
    }, 300);

    return () => window.clearTimeout(saveTimer);
  }, [workspace, workspaceReady]);

  useEffect(() => {
    const controller = new AbortController();
    void client.checkConnection(controller.signal);

    return () => controller.abort();
  }, [client]);

  const createProject = (): void => {
    setWorkspace((current) => {
      const project = createWorkspaceProject(
        `Nuevo diseño ${current.projects.length + 1}`,
      );

      return {
        ...current,
        activeProjectId: project.id,
        projects: [project, ...current.projects],
      };
    });
    setStorageError(null);
    setCameraDistance(1);
    setResetVersion((value) => value + 1);
  };

  const selectProject = (projectId: string): void => {
    setWorkspace((current) => ({
      ...current,
      activeProjectId: projectId,
    }));
    setStorageError(null);
    setCameraDistance(1);
    setResetVersion((value) => value + 1);
  };

  const renameProject = (projectId: string, name: string): void => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      return;
    }

    updateProject(
      projectId,
      (project) => ({
        ...project,
        name: trimmedName,
        notice: "Proyecto renombrado",
      }),
      true,
    );
  };

  const deleteProject = async (projectId: string): Promise<void> => {
    const project = projects.find((candidate) => candidate.id === projectId);
    if (!project) {
      return;
    }

    const confirmed = window.confirm(
      `¿Eliminar “${project.name}”?\n\nSe borrarán también sus adjuntos locales. Esta acción no se puede deshacer.`,
    );
    if (!confirmed) {
      return;
    }

    try {
      await workspaceStore.removeProjectData(projectId);
      setWorkspace((current) => {
        const remainingProjects = current.projects.filter(
          (candidate) => candidate.id !== projectId,
        );
        if (remainingProjects.length === 0) {
          const replacement = createWorkspaceProject("Nuevo diseño 1");
          return {
            ...current,
            activeProjectId: replacement.id,
            projects: [replacement],
          };
        }

        return {
          ...current,
          activeProjectId:
            current.activeProjectId === projectId
              ? remainingProjects[0].id
              : current.activeProjectId,
          projects: remainingProjects,
        };
      });
      setStorageError(null);
      setCameraDistance(1);
      setResetVersion((value) => value + 1);
    } catch (error) {
      setStorageError(
        error instanceof Error
          ? `No se pudo eliminar el proyecto: ${error.message}`
          : "No se pudo eliminar el proyecto",
      );
    }
  };

  const handleProgress = (
    projectId: string,
    event: PipelineProgressEvent,
  ): void => {
    updateProject(projectId, (project) => ({
      ...project,
      currentStage: event.stageIndex,
      completedStage: event.stageIndex - 1,
      notice: event.message,
    }));
  };

  const runGeneration = async (requestMessage?: string): Promise<void> => {
    if (isGenerating) {
      return;
    }

    const projectId = activeProject.id;
    const attachmentNames = activeProject.attachments.map(
      (attachment) => attachment.name,
    );
    const prompt =
      requestMessage?.trim() ||
      activeProject.draft.trim() ||
      "Genera una carcasa funcional a partir de la especificación.";
    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsGenerating(true);
    updateProject(
      projectId,
      (project) => ({
        ...project,
        name: project.name.startsWith("Nuevo diseño ")
          ? deriveProjectName(prompt)
          : project.name,
        draft: "",
        completedStage: -1,
        currentStage: 0,
        notice: "Preparando la petición",
        conversation: [
          ...project.conversation,
          createConversationEntry("user", prompt, attachmentNames),
        ],
      }),
      true,
    );

    try {
      const generationResult = await client.generate(
        {
          projectId,
          message: prompt,
          attachmentNames,
          requestedFormats: ["STEP", "STL", "3MF"],
        },
        (event) => handleProgress(projectId, event),
        controller.signal,
      );

      const hasRealArtifacts = generationResult.artifacts.some(
        (artifact) => artifact.downloadUrl,
      );
      const completionNotice = hasRealArtifacts
        ? "Modelo real generado y validado"
        : "Simulación completada · backend no conectado";
      updateProject(
        projectId,
        (project) => ({
          ...project,
          result: generationResult,
          completedStage: PIPELINE_STAGES.length - 1,
          currentStage: PIPELINE_STAGES.length - 1,
          notice: completionNotice,
          conversation: [
            ...project.conversation,
            createConversationEntry(
              "assistant",
              hasRealArtifacts
                ? "He generado y validado el modelo. Los archivos de fabricación ya están disponibles."
                : "He completado la demostración del flujo. El modelo real se generará cuando el backend esté conectado.",
            ),
          ],
        }),
        true,
      );
    } catch (error) {
      if (
        !(error instanceof DOMException) ||
        error.name !== "AbortError"
      ) {
        const errorMessage =
          error instanceof Error
            ? error.message
            : "No se pudo completar la generación";
        updateProject(
          projectId,
          (project) => ({
            ...project,
            notice: errorMessage,
            conversation: [
              ...project.conversation,
              createConversationEntry(
                "assistant",
                `No he podido completar la petición: ${errorMessage}`,
              ),
            ],
          }),
        );
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const pickAttachments = async (): Promise<void> => {
    const projectId = activeProject.id;
    setProjectNotice(projectId, "Seleccionando archivos...");

    try {
      const selected = await workspaceStore.pickAttachments(projectId);
      if (selected.length === 0) {
        setProjectNotice(projectId, "No se añadió ningún archivo");
        return;
      }

      updateProject(
        projectId,
        (project) => ({
          ...project,
          attachments: [...project.attachments, ...selected],
          notice:
            selected.length === 1
              ? `${selected[0].name} guardado en el proyecto`
              : `${selected.length} archivos guardados en el proyecto`,
        }),
        true,
      );
    } catch (error) {
      setProjectNotice(
        projectId,
        error instanceof Error
          ? error.message
          : "No se pudieron adjuntar los archivos",
      );
    }
  };

  const removeAttachment = async (
    attachment: WorkspaceAttachment,
  ): Promise<void> => {
    const projectId = activeProject.id;

    try {
      await workspaceStore.removeAttachment(projectId, attachment);
      updateProject(
        projectId,
        (project) => ({
          ...project,
          attachments: project.attachments.filter(
            (candidate) => candidate.id !== attachment.id,
          ),
          notice: `${attachment.name} eliminado del proyecto`,
        }),
        true,
      );
    } catch (error) {
      setProjectNotice(
        projectId,
        error instanceof Error
          ? error.message
          : "No se pudo eliminar el archivo",
      );
    }
  };

  const openAttachment = async (
    attachment: WorkspaceAttachment,
  ): Promise<void> => {
    const projectId = activeProject.id;

    try {
      const opened = await workspaceStore.openAttachment(
        projectId,
        attachment,
      );
      setProjectNotice(
        projectId,
        opened
          ? `${attachment.name} abierto`
          : `No se pudo abrir ${attachment.name}`,
      );
    } catch (error) {
      setProjectNotice(
        projectId,
        error instanceof Error
          ? error.message
          : "No se pudo abrir el archivo",
      );
    }
  };

  const downloadArtifact = async (
    artifact: ExportArtifact,
  ): Promise<number> => {
    const files =
      artifact.files && artifact.files.length > 0
        ? artifact.files
        : artifact.downloadUrl
          ? [
              {
                partId: "model",
                label: "Modelo",
                fileName: artifact.fileName,
                downloadUrl: artifact.downloadUrl,
              },
            ]
          : [];

    if (files.length === 0) {
      setProjectNotice(
        activeProject.id,
        "La exportación estará disponible al conectar el backend",
      );
      return 0;
    }

    setProjectNotice(
      activeProject.id,
      files.length === 1
        ? `Preparando ${files[0].fileName}...`
        : `Preparando ${files.length} archivos ${artifact.format}...`,
    );

    if (window.modelIADesktop?.saveExportFiles) {
      const result = await window.modelIADesktop.saveExportFiles(
        files.map((file) => ({
          fileName: file.fileName,
          downloadUrl: file.downloadUrl,
        })),
      );
      return result.canceled ? 0 : result.savedFileNames.length;
    }

    for (const file of files) {
      const response = await fetch(file.downloadUrl);
      if (!response.ok) {
        throw new Error(`No se pudo descargar ${file.fileName}`);
      }

      const blobUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = file.fileName;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    }

    return files.length;
  };

  const handleExport = async (
    format: "STEP" | "STL" | "3MF",
  ): Promise<void> => {
    const artifact = activeProject.result.artifacts.find(
      (candidate) => candidate.format === format,
    );

    if (artifact) {
      try {
        const downloadedFiles = await downloadArtifact(artifact);
        if (downloadedFiles === 0) {
          return;
        }
        setProjectNotice(
          activeProject.id,
          downloadedFiles === 1
            ? `${artifact.fileName} descargado`
            : `${downloadedFiles} archivos ${artifact.format} descargados`,
        );
      } catch (error) {
        setProjectNotice(
          activeProject.id,
          error instanceof Error
            ? error.message
            : "No se pudo descargar el archivo",
        );
      }
    }
  };

  const resetView = (): void => {
    setCameraDistance(1);
    setResetVersion((value) => value + 1);
  };

  const enterFullscreen = (): void => {
    void viewerRef.current?.requestFullscreen();
  };

  return (
    <div className="app-shell">
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        managementDisabled={isGenerating}
        onCreateProject={createProject}
        onDeleteProject={deleteProject}
        onRenameProject={renameProject}
        onSelectProject={selectProject}
      />

      <main className="main-content">
        <header className="topbar">
          <h1>
            <span>Diseñando:</span> {activeProject.name}
          </h1>

          <Pipeline
            completedStage={activeProject.completedStage}
            currentStage={activeProject.currentStage}
            isGenerating={isGenerating}
          />

          <button
            className="generate-button"
            type="button"
            disabled={isGenerating}
            onClick={() => void runGeneration()}
          >
            <Sparkles size={19} />
            {isGenerating ? "Generando..." : "Generar modelo"}
          </button>
        </header>

        <div className="workspace">
          <div className="center-column">
            <section
              className="viewer-panel"
              ref={viewerRef}
            >
              <div className="panel-label">
                <BoxIcon size={18} />
                Vista 3D
              </div>
              <div className="viewer-status">
                <span
                  className={`status-dot${
                    isGenerating ? " pulsing" : ` ${connection.mode}`
                  }`}
                />
                {isGenerating ? "Actualizando modelo" : connection.label}
              </div>

              <ViewerScene
                autoRotate={autoRotate}
                exploded={exploded}
                distance={cameraDistance}
                resetVersion={resetVersion}
                preview={activeProject.result.preview}
              />

              <ViewerToolbar
                autoRotate={autoRotate}
                exploded={exploded}
                onReset={resetView}
                onToggleRotate={() =>
                  setAutoRotate((value) => !value)
                }
                onToggleExploded={() =>
                  setExploded((value) => !value)
                }
                onZoomIn={() =>
                  setCameraDistance((value) =>
                    Math.max(0.72, value - 0.12),
                  )
                }
                onZoomOut={() =>
                  setCameraDistance((value) =>
                    Math.min(1.55, value + 0.12),
                  )
                }
                onFullscreen={enterFullscreen}
              />

              <div className="axis-indicator">
                <i className="axis-y" />
                <i className="axis-x" />
                <i className="axis-z" />
                <span className="axis-label-y">Y</span>
                <span className="axis-label-x">X</span>
                <span className="axis-label-z">Z</span>
              </div>
            </section>

            <Composer
              value={activeProject.draft}
              attachments={activeProject.attachments}
              conversation={activeProject.conversation}
              notice={
                storageError ??
                (workspaceReady
                  ? activeProject.notice
                  : "Recuperando proyectos...")
              }
              isGenerating={isGenerating}
              onChange={(draft) =>
                updateProject(activeProject.id, (project) => ({
                  ...project,
                  draft,
                }))
              }
              onAttach={pickAttachments}
              onOpenAttachment={openAttachment}
              onRemoveAttachment={removeAttachment}
              onSubmit={() => void runGeneration(activeProject.draft)}
            />
          </div>

          <Inspector
            result={activeProject.result}
            onExport={handleExport}
          />
        </div>
      </main>
    </div>
  );
}
