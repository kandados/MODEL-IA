export const PIPELINE_STAGES = [
  {
    id: "interpret",
    label: "Interpretar",
    progressLabel: "Interpretando la petición",
  },
  {
    id: "design",
    label: "Diseñar",
    progressLabel: "Construyendo el diseño paramétrico",
  },
  {
    id: "validate",
    label: "Validar",
    progressLabel: "Validando geometría e imprimibilidad",
  },
  {
    id: "export",
    label: "Exportar",
    progressLabel: "Preparando archivos de fabricación",
  },
] as const;

export type PipelineStageId =
  (typeof PIPELINE_STAGES)[number]["id"];

export type ClientMode = "checking" | "live" | "demo";

export interface ClientConnection {
  mode: ClientMode;
  label: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  updatedAt: string;
}

export interface GenerationRequest {
  projectId: string;
  message: string;
  attachmentNames: string[];
  requestedFormats: Array<"STEP" | "STL" | "3MF">;
}

export interface PipelineProgressEvent {
  stage: PipelineStageId;
  stageIndex: number;
  progress: number;
  message: string;
}

export interface DesignSpecification {
  dimensions: {
    widthMm: number;
    depthMm: number;
    heightMm: number;
  };
  material: string;
  toleranceMm: number;
}

export interface ValidationItem {
  id: string;
  label: string;
  status: "passed" | "warning" | "error";
}

export interface ExportArtifact {
  format: "STEP" | "STL" | "3MF";
  fileName: string;
  available: boolean;
  downloadUrl?: string;
}

export interface ModelPreview {
  format: "STL";
  url: string;
}

export interface GenerationResult {
  projectId: string;
  status: "completed";
  specification: DesignSpecification;
  validations: ValidationItem[];
  artifacts: ExportArtifact[];
  preview?: ModelPreview;
}

export interface ModelIAClient {
  generate(
    request: GenerationRequest,
    onProgress: (event: PipelineProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<GenerationResult>;
}

type ConnectionListener = (connection: ClientConnection) => void;

interface GenerationAccepted {
  generationId: string;
  websocketUrl?: string;
}

type JsonRecord = Record<string, unknown>;

const DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1";

const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null;

const readString = (
  value: JsonRecord,
  camelCaseKey: string,
  snakeCaseKey: string = camelCaseKey,
): string | undefined => {
  const candidate = value[camelCaseKey] ?? value[snakeCaseKey];
  return typeof candidate === "string" ? candidate : undefined;
};

const readNumber = (
  value: JsonRecord,
  camelCaseKey: string,
  snakeCaseKey: string = camelCaseKey,
): number | undefined => {
  const candidate = value[camelCaseKey] ?? value[snakeCaseKey];
  return typeof candidate === "number" && Number.isFinite(candidate)
    ? candidate
    : undefined;
};

const resolveUrl = (value: string, baseUrl: string): string =>
  new URL(value, `${baseUrl.replace(/\/$/, "")}/`).toString();

const resolveApiUrl = (): string => {
  const configuredUrl = import.meta.env.VITE_MODEL_IA_API_URL?.trim();
  return (configuredUrl || DEFAULT_API_URL).replace(/\/$/, "");
};

const wait = (
  durationMs: number,
  signal?: AbortSignal,
): Promise<void> =>
  new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, durationMs);

    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Generación cancelada", "AbortError"));
      },
      { once: true },
    );
  });

const fetchWithTimeout = async (
  input: RequestInfo | URL,
  init: RequestInit,
  durationMs: number,
  externalSignal?: AbortSignal,
): Promise<Response> => {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), durationMs);
  const abortFromExternalSignal = (): void => controller.abort();

  externalSignal?.addEventListener("abort", abortFromExternalSignal, {
    once: true,
  });

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromExternalSignal);
  }
};

const responseError = async (response: Response): Promise<Error> => {
  let detail = `El backend respondió con HTTP ${response.status}.`;

  try {
    const payload: unknown = await response.json();
    if (isRecord(payload)) {
      const candidate = payload.detail ?? payload.message;
      if (typeof candidate === "string" && candidate.trim()) {
        detail = candidate;
      }
    }
  } catch {
    // La respuesta puede no contener JSON. Se conserva el mensaje HTTP.
  }

  return new Error(detail);
};

const normalizeStage = (
  stageValue: unknown,
  stageIndexValue: unknown,
): { stage: PipelineStageId; stageIndex: number } => {
  const aliases: Record<string, PipelineStageId> = {
    interpret: "interpret",
    interpretation: "interpret",
    research: "interpret",
    knowledge: "design",
    plan: "design",
    planning: "design",
    design: "design",
    cad: "design",
    generate: "design",
    validate: "validate",
    validation: "validate",
    export: "export",
    exporting: "export",
  };

  const normalizedName =
    typeof stageValue === "string"
      ? aliases[stageValue.trim().toLowerCase()]
      : undefined;
  const numericIndex =
    typeof stageIndexValue === "number"
      ? Math.max(
          0,
          Math.min(PIPELINE_STAGES.length - 1, stageIndexValue),
        )
      : undefined;
  const stage =
    normalizedName ?? PIPELINE_STAGES[numericIndex ?? 0].id;
  const stageIndex = PIPELINE_STAGES.findIndex(
    (candidate) => candidate.id === stage,
  );

  return { stage, stageIndex };
};

const normalizeResult = (
  rawValue: unknown,
  apiBaseUrl: string,
): GenerationResult => {
  if (!isRecord(rawValue)) {
    throw new Error("El backend devolvió un resultado CAD no válido.");
  }

  const rawSpecification = rawValue.specification;
  const specification = isRecord(rawSpecification)
    ? rawSpecification
    : {};
  const rawDimensions = specification.dimensions;
  const dimensions = isRecord(rawDimensions) ? rawDimensions : {};
  const rawValidations = Array.isArray(rawValue.validations)
    ? rawValue.validations
    : [];
  const rawArtifacts = Array.isArray(rawValue.artifacts)
    ? rawValue.artifacts
    : [];

  const artifacts = rawArtifacts.flatMap((candidate): ExportArtifact[] => {
    if (!isRecord(candidate)) {
      return [];
    }

    const format = readString(candidate, "format")?.toUpperCase();
    if (format !== "STEP" && format !== "STL" && format !== "3MF") {
      return [];
    }

    const fileName =
      readString(candidate, "fileName", "file_name") ??
      `model_ia.${format.toLowerCase()}`;
    const rawDownloadUrl = readString(
      candidate,
      "downloadUrl",
      "download_url",
    );

    return [
      {
        format,
        fileName,
        available:
          typeof candidate.available === "boolean"
            ? candidate.available
            : Boolean(rawDownloadUrl),
        downloadUrl: rawDownloadUrl
          ? resolveUrl(rawDownloadUrl, apiBaseUrl)
          : undefined,
      },
    ];
  });

  const validations = rawValidations.flatMap(
    (candidate, index): ValidationItem[] => {
      if (!isRecord(candidate)) {
        return [];
      }

      const rawStatus = readString(candidate, "status");
      const status =
        rawStatus === "warning" || rawStatus === "error"
          ? rawStatus
          : "passed";

      return [
        {
          id:
            readString(candidate, "id") ??
            readString(candidate, "code") ??
            `validation-${index + 1}`,
          label:
            readString(candidate, "label") ??
            readString(candidate, "message") ??
            "Validación completada",
          status,
        },
      ];
    },
  );

  const rawPreview = rawValue.preview;
  const previewUrl = isRecord(rawPreview)
    ? readString(rawPreview, "url")
    : undefined;
  const stlArtifact = artifacts.find(
    (artifact) => artifact.format === "STL" && artifact.downloadUrl,
  );
  const resolvedPreviewUrl = previewUrl
    ? resolveUrl(previewUrl, apiBaseUrl)
    : stlArtifact?.downloadUrl;

  return {
    projectId:
      readString(rawValue, "projectId", "project_id") ?? "project",
    status: "completed",
    specification: {
      dimensions: {
        widthMm:
          readNumber(dimensions, "widthMm", "width_mm") ?? 0,
        depthMm:
          readNumber(dimensions, "depthMm", "depth_mm") ?? 0,
        heightMm:
          readNumber(dimensions, "heightMm", "height_mm") ?? 0,
      },
      material: readString(specification, "material") ?? "Sin definir",
      toleranceMm:
        readNumber(specification, "toleranceMm", "tolerance_mm") ?? 0,
    },
    validations,
    artifacts,
    preview: resolvedPreviewUrl
      ? {
          format: "STL",
          url: resolvedPreviewUrl,
        }
      : undefined,
  };
};

const parseAcceptedGeneration = (rawValue: unknown): GenerationAccepted => {
  if (!isRecord(rawValue)) {
    throw new Error("El backend no devolvió un identificador de generación.");
  }

  const generationId =
    readString(rawValue, "generationId", "generation_id") ??
    readString(rawValue, "jobId", "job_id") ??
    readString(rawValue, "id");

  if (!generationId) {
    throw new Error("El backend no devolvió un identificador de generación.");
  }

  return {
    generationId,
    websocketUrl: readString(
      rawValue,
      "websocketUrl",
      "websocket_url",
    ),
  };
};

export class MockModelIAClient implements ModelIAClient {
  async generate(
    request: GenerationRequest,
    onProgress: (event: PipelineProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<GenerationResult> {
    for (const [stageIndex, stage] of PIPELINE_STAGES.entries()) {
      onProgress({
        stage: stage.id,
        stageIndex,
        progress: stageIndex / PIPELINE_STAGES.length,
        message: stage.progressLabel,
      });

      await wait(stage.id === "design" ? 1000 : 700, signal);
    }

    return {
      projectId: request.projectId,
      status: "completed",
      specification: {
        dimensions: {
          widthMm: 210,
          depthMm: 210,
          heightMm: 52,
        },
        material: "PETG",
        toleranceMm: 0.5,
      },
      validations: [
        {
          id: "closed-geometry",
          label: "Geometría correcta",
          status: "passed",
        },
        {
          id: "print-ready",
          label: "Lista para imprimir",
          status: "passed",
        },
      ],
      artifacts: request.requestedFormats.map((format) => ({
        format,
        fileName: `carcasa_mac_mini.${format.toLowerCase()}`,
        available: false,
      })),
    };
  }
}

export class HttpModelIAClient implements ModelIAClient {
  constructor(private readonly apiBaseUrl = resolveApiUrl()) {}

  async isAvailable(signal?: AbortSignal): Promise<boolean> {
    try {
      const response = await fetchWithTimeout(
        `${this.apiBaseUrl}/health`,
        {
          method: "GET",
          cache: "no-store",
          headers: {
            Accept: "application/json",
          },
        },
        1500,
        signal,
      );

      return response.ok;
    } catch {
      return false;
    }
  }

  async generate(
    request: GenerationRequest,
    onProgress: (event: PipelineProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<GenerationResult> {
    const response = await fetch(`${this.apiBaseUrl}/generations`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        project_id: request.projectId,
        message: request.message,
        attachment_names: request.attachmentNames,
        requested_formats: request.requestedFormats,
      }),
      signal,
    });

    if (!response.ok) {
      throw await responseError(response);
    }

    const payload: unknown = await response.json();

    if (
      isRecord(payload) &&
      payload.status === "completed" &&
      Array.isArray(payload.artifacts)
    ) {
      return normalizeResult(payload, this.apiBaseUrl);
    }

    return this.waitForGeneration(
      parseAcceptedGeneration(payload),
      onProgress,
      signal,
    );
  }

  private waitForGeneration(
    accepted: GenerationAccepted,
    onProgress: (event: PipelineProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<GenerationResult> {
    const httpUrl =
      accepted.websocketUrl ??
      `${this.apiBaseUrl}/generations/${accepted.generationId}/events`;
    const socketUrl = new URL(resolveUrl(httpUrl, this.apiBaseUrl));
    socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";

    return new Promise((resolve, reject) => {
      const socket = new WebSocket(socketUrl);
      let settled = false;

      const cleanup = (): void => {
        signal?.removeEventListener("abort", handleAbort);
        socket.close();
      };

      const finish = (
        handler: () => void,
      ): void => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        handler();
      };

      const handleAbort = (): void => {
        finish(() =>
          reject(new DOMException("Generación cancelada", "AbortError")),
        );
      };

      signal?.addEventListener("abort", handleAbort, { once: true });

      socket.addEventListener("message", (messageEvent) => {
        try {
          const event: unknown = JSON.parse(String(messageEvent.data));
          if (!isRecord(event)) {
            return;
          }

          const eventType = readString(event, "type")?.toLowerCase();

          if (eventType === "progress") {
            const normalizedStage = normalizeStage(
              event.stage,
              event.stageIndex ?? event.stage_index,
            );
            onProgress({
              ...normalizedStage,
              progress:
                readNumber(event, "progress") ??
                normalizedStage.stageIndex / PIPELINE_STAGES.length,
              message:
                readString(event, "message") ??
                PIPELINE_STAGES[normalizedStage.stageIndex].progressLabel,
            });
            return;
          }

          if (eventType === "completed") {
            finish(() =>
              resolve(
                normalizeResult(
                  event.result ?? event.data,
                  this.apiBaseUrl,
                ),
              ),
            );
            return;
          }

          if (eventType === "failed" || eventType === "error") {
            finish(() =>
              reject(
                new Error(
                  readString(event, "message") ??
                    "El backend no pudo completar la generación.",
                ),
              ),
            );
          }
        } catch (error) {
          finish(() =>
            reject(
              error instanceof Error
                ? error
                : new Error("Evento WebSocket no válido."),
            ),
          );
        }
      });

      socket.addEventListener("error", () => {
        finish(() =>
          reject(new Error("No se pudo abrir el canal del backend.")),
        );
      });
    });
  }
}

export class AdaptiveModelIAClient implements ModelIAClient {
  private readonly httpClient = new HttpModelIAClient();
  private readonly mockClient = new MockModelIAClient();

  constructor(private readonly onConnectionChange: ConnectionListener) {}

  async checkConnection(signal?: AbortSignal): Promise<ClientConnection> {
    this.onConnectionChange({
      mode: "checking",
      label: "Comprobando backend",
    });

    const live = await this.httpClient.isAvailable(signal);
    const connection: ClientConnection = live
      ? {
          mode: "live",
          label: "Backend conectado",
        }
      : {
          mode: "demo",
          label: "Modo demostración",
        };

    if (!signal?.aborted) {
      this.onConnectionChange(connection);
    }

    return connection;
  }

  async generate(
    request: GenerationRequest,
    onProgress: (event: PipelineProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<GenerationResult> {
    const connection = await this.checkConnection(signal);

    if (signal?.aborted) {
      throw new DOMException("Generación cancelada", "AbortError");
    }

    const activeClient =
      connection.mode === "live" ? this.httpClient : this.mockClient;

    return activeClient.generate(request, onProgress, signal);
  }
}

export const initialProjects: ProjectSummary[] = [
  {
    id: "mac-mini-case",
    name: "Carcasa Mac mini",
    updatedAt: "Ahora",
  },
  {
    id: "dual-support",
    name: "Soporte doble",
    updatedAt: "Ayer",
  },
  {
    id: "electronics-box",
    name: "Caja electrónica",
    updatedAt: "28 jul",
  },
];

export const initialResult: GenerationResult = {
  projectId: "mac-mini-case",
  status: "completed",
  specification: {
    dimensions: {
      widthMm: 210,
      depthMm: 210,
      heightMm: 52,
    },
    material: "PETG",
    toleranceMm: 0.5,
  },
  validations: [
    {
      id: "closed-geometry",
      label: "Geometría correcta",
      status: "passed",
    },
    {
      id: "print-ready",
      label: "Lista para imprimir",
      status: "passed",
    },
  ],
  artifacts: [
    {
      format: "STEP",
      fileName: "carcasa_mac_mini.step",
      available: false,
    },
    {
      format: "STL",
      fileName: "carcasa_mac_mini.stl",
      available: false,
    },
    {
      format: "3MF",
      fileName: "carcasa_mac_mini.3mf",
      available: false,
    },
  ],
};
