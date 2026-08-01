import {
  initialProjects,
  initialResult,
  type GenerationResult,
  type ProjectSummary,
} from "./model-ia-client";

export interface WorkspaceAttachment {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  storedName: string;
  addedAt: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  attachmentNames: string[];
}

export interface WorkspaceProject extends ProjectSummary {
  createdAt: string;
  draft: string;
  attachments: WorkspaceAttachment[];
  conversation: ConversationMessage[];
  result: GenerationResult;
  completedStage: number;
  currentStage: number;
  notice: string;
}

export interface WorkspaceSnapshot {
  version: 1;
  activeProjectId: string;
  projects: WorkspaceProject[];
}

type JsonRecord = Record<string, unknown>;

const BROWSER_STORAGE_KEY = "model-ia-workspace-v1";

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null;

const cloneResult = (
  source: GenerationResult,
  projectId: string,
): GenerationResult => ({
  ...source,
  projectId,
  specification: {
    ...source.specification,
    dimensions: { ...source.specification.dimensions },
  },
  validations: source.validations.map((validation) => ({ ...validation })),
  artifacts: source.artifacts.map((artifact) => ({
    ...artifact,
    files: artifact.files?.map((file) => ({ ...file })),
  })),
  preview: source.preview
    ? {
        ...source.preview,
        parts: source.preview.parts?.map((part) => ({
          ...part,
          assembledPositionMm: [...part.assembledPositionMm],
          explodedPositionMm: [...part.explodedPositionMm],
        })),
      }
    : undefined,
});

export const createEmptyResult = (projectId: string): GenerationResult => ({
  projectId,
  status: "completed",
  specification: {
    dimensions: {
      widthMm: 0,
      depthMm: 0,
      heightMm: 0,
    },
    material: "Por definir",
    toleranceMm: 0,
  },
  validations: [],
  artifacts: (["STEP", "STL", "3MF"] as const).map((format) => ({
    format,
    fileName: `modelo.${format.toLowerCase()}`,
    available: false,
  })),
});

const createGreeting = (content: string): ConversationMessage => ({
  id: crypto.randomUUID(),
  role: "assistant",
  content,
  createdAt: new Date().toISOString(),
  attachmentNames: [],
});

export const createInitialWorkspace = (): WorkspaceSnapshot => {
  const now = Date.now();
  const projects = initialProjects.map((project, index): WorkspaceProject => {
    const timestamp = new Date(now - index * 86_400_000).toISOString();

    return {
      ...project,
      updatedAt: timestamp,
      createdAt: timestamp,
      draft: "",
      attachments: [],
      conversation: [
        createGreeting(
          index === 0
            ? "Diseño cargado. Puedes pedirme un cambio o adjuntar una referencia."
            : "Proyecto listo para continuar cuando quieras.",
        ),
      ],
      result: cloneResult(initialResult, project.id),
      completedStage: 2,
      currentStage: 3,
      notice: index === 0 ? "Diseño listo para revisar" : "Proyecto guardado",
    };
  });

  return {
    version: 1,
    activeProjectId: projects[0].id,
    projects,
  };
};

export const createWorkspaceProject = (
  name: string,
): WorkspaceProject => {
  const id = `project-${crypto.randomUUID()}`;
  const timestamp = new Date().toISOString();

  return {
    id,
    name,
    createdAt: timestamp,
    updatedAt: timestamp,
    draft: "",
    attachments: [],
    conversation: [
      createGreeting(
        "Nuevo proyecto creado. Describe la pieza que quieres fabricar o adjunta una referencia.",
      ),
    ],
    result: createEmptyResult(id),
    completedStage: -1,
    currentStage: 0,
    notice: "Describe la pieza que quieres crear",
  };
};

const isGenerationResult = (
  value: unknown,
): value is GenerationResult => {
  if (!isRecord(value) || !isRecord(value.specification)) {
    return false;
  }

  return (
    value.status === "completed" &&
    isRecord(value.specification.dimensions) &&
    Array.isArray(value.validations) &&
    Array.isArray(value.artifacts)
  );
};

const normalizeAttachment = (
  value: unknown,
): WorkspaceAttachment | null => {
  if (!isRecord(value)) {
    return null;
  }

  const { id, name, size, mimeType, storedName, addedAt } = value;
  if (
    typeof id !== "string" ||
    typeof name !== "string" ||
    typeof size !== "number" ||
    typeof mimeType !== "string" ||
    typeof storedName !== "string" ||
    typeof addedAt !== "string"
  ) {
    return null;
  }

  return { id, name, size, mimeType, storedName, addedAt };
};

const normalizeMessage = (
  value: unknown,
): ConversationMessage | null => {
  if (!isRecord(value)) {
    return null;
  }

  const { id, role, content, createdAt, attachmentNames } = value;
  if (
    typeof id !== "string" ||
    (role !== "user" && role !== "assistant") ||
    typeof content !== "string" ||
    typeof createdAt !== "string"
  ) {
    return null;
  }

  return {
    id,
    role,
    content,
    createdAt,
    attachmentNames: Array.isArray(attachmentNames)
      ? attachmentNames.filter(
          (candidate): candidate is string => typeof candidate === "string",
        )
      : [],
  };
};

const normalizeProject = (value: unknown): WorkspaceProject | null => {
  if (!isRecord(value)) {
    return null;
  }

  const { id, name, createdAt, updatedAt } = value;
  if (
    typeof id !== "string" ||
    typeof name !== "string" ||
    typeof createdAt !== "string" ||
    typeof updatedAt !== "string"
  ) {
    return null;
  }

  const attachments = Array.isArray(value.attachments)
    ? value.attachments.flatMap((attachment) => {
        const normalized = normalizeAttachment(attachment);
        return normalized ? [normalized] : [];
      })
    : [];
  const conversation = Array.isArray(value.conversation)
    ? value.conversation.flatMap((message) => {
        const normalized = normalizeMessage(message);
        return normalized ? [normalized] : [];
      })
    : [];

  return {
    id,
    name,
    createdAt,
    updatedAt,
    draft: typeof value.draft === "string" ? value.draft : "",
    attachments,
    conversation:
      conversation.length > 0
        ? conversation
        : [createGreeting("Proyecto recuperado.")],
    result: isGenerationResult(value.result)
      ? cloneResult(value.result, id)
      : createEmptyResult(id),
    completedStage:
      typeof value.completedStage === "number" ? value.completedStage : -1,
    currentStage:
      typeof value.currentStage === "number" ? value.currentStage : 0,
    notice:
      typeof value.notice === "string" ? value.notice : "Proyecto recuperado",
  };
};

const normalizeWorkspace = (value: unknown): WorkspaceSnapshot | null => {
  if (!isRecord(value) || !Array.isArray(value.projects)) {
    return null;
  }

  const projects = value.projects.flatMap((project) => {
    const normalized = normalizeProject(project);
    return normalized ? [normalized] : [];
  });

  if (projects.length === 0) {
    return null;
  }

  const requestedActiveId =
    typeof value.activeProjectId === "string" ? value.activeProjectId : "";
  const activeProjectId = projects.some(
    (project) => project.id === requestedActiveId,
  )
    ? requestedActiveId
    : projects[0].id;

  return {
    version: 1,
    activeProjectId,
    projects,
  };
};

const readBrowserWorkspace = (): unknown => {
  try {
    const serialized = localStorage.getItem(BROWSER_STORAGE_KEY);
    return serialized ? JSON.parse(serialized) : null;
  } catch {
    return null;
  }
};

export const workspaceStore = {
  async load(): Promise<WorkspaceSnapshot> {
    const rawWorkspace = window.modelIADesktop
      ? await window.modelIADesktop.loadWorkspace()
      : readBrowserWorkspace();

    return normalizeWorkspace(rawWorkspace) ?? createInitialWorkspace();
  },

  async save(workspace: WorkspaceSnapshot): Promise<void> {
    if (window.modelIADesktop) {
      await window.modelIADesktop.saveWorkspace(workspace);
      return;
    }

    localStorage.setItem(BROWSER_STORAGE_KEY, JSON.stringify(workspace));
  },

  async pickAttachments(projectId: string): Promise<WorkspaceAttachment[]> {
    if (!window.modelIADesktop) {
      return [];
    }

    const result = await window.modelIADesktop.pickAttachments(projectId);
    if (!Array.isArray(result)) {
      return [];
    }

    return result.flatMap((attachment) => {
      const normalized = normalizeAttachment(attachment);
      return normalized ? [normalized] : [];
    });
  },

  async removeAttachment(
    projectId: string,
    attachment: WorkspaceAttachment,
  ): Promise<boolean> {
    if (!window.modelIADesktop) {
      return true;
    }

    return window.modelIADesktop.removeAttachment(
      projectId,
      attachment.storedName,
    );
  },

  async openAttachment(
    projectId: string,
    attachment: WorkspaceAttachment,
  ): Promise<boolean> {
    if (!window.modelIADesktop) {
      return false;
    }

    return window.modelIADesktop.openAttachment(
      projectId,
      attachment.storedName,
    );
  },

  async removeProjectData(projectId: string): Promise<boolean> {
    if (!window.modelIADesktop) {
      return true;
    }

    return window.modelIADesktop.removeProjectData(projectId);
  },
};
