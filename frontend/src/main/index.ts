import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  shell,
  type IpcMainInvokeEvent,
  type OpenDialogOptions,
} from "electron";
import {
  copyFile,
  mkdir,
  readFile,
  rm,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { basename, extname, join } from "node:path";

const WORKSPACE_FILE_NAME = "workspace-v1.json";
const MAX_WORKSPACE_BYTES = 5 * 1024 * 1024;
const PROJECT_ID_PATTERN = /^[a-zA-Z0-9_-]{1,100}$/;
const ALLOWED_ATTACHMENT_EXTENSIONS = new Set([
  ".3mf",
  ".dxf",
  ".jpeg",
  ".jpg",
  ".obj",
  ".pdf",
  ".png",
  ".step",
  ".stl",
  ".stp",
  ".svg",
  ".webp",
]);

const MIME_TYPES: Record<string, string> = {
  ".3mf": "model/3mf",
  ".dxf": "image/vnd.dxf",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".obj": "model/obj",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".step": "model/step",
  ".stl": "model/stl",
  ".stp": "model/step",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
};

app.setName("Model-IA");

const getWorkspacePath = (): string =>
  join(app.getPath("userData"), WORKSPACE_FILE_NAME);

const getProjectAttachmentDirectory = (projectId: string): string => {
  if (!PROJECT_ID_PATTERN.test(projectId)) {
    throw new Error("El identificador del proyecto no es válido.");
  }

  return join(app.getPath("userData"), "projects", projectId, "attachments");
};

const getProjectDirectory = (projectId: string): string => {
  if (!PROJECT_ID_PATTERN.test(projectId)) {
    throw new Error("El identificador del proyecto no es válido.");
  }

  return join(app.getPath("userData"), "projects", projectId);
};

const getStoredAttachmentPath = (
  projectId: string,
  storedName: string,
): string => {
  if (basename(storedName) !== storedName || !storedName.trim()) {
    throw new Error("El archivo adjunto no es válido.");
  }

  return join(getProjectAttachmentDirectory(projectId), storedName);
};

const getParentWindow = (
  event: IpcMainInvokeEvent,
): BrowserWindow | undefined =>
  BrowserWindow.fromWebContents(event.sender) ?? undefined;

const registerDesktopHandlers = (): void => {
  ipcMain.handle("model-ia:workspace:load", async () => {
    try {
      return JSON.parse(await readFile(getWorkspacePath(), "utf8")) as unknown;
    } catch (error) {
      if (
        error instanceof Error &&
        "code" in error &&
        error.code === "ENOENT"
      ) {
        return null;
      }

      throw error;
    }
  });

  ipcMain.handle(
    "model-ia:workspace:save",
    async (_event, workspace: unknown) => {
      const serialized = JSON.stringify(workspace, null, 2);
      if (Buffer.byteLength(serialized, "utf8") > MAX_WORKSPACE_BYTES) {
        throw new Error("El proyecto supera el tamaño permitido para sus datos.");
      }

      await mkdir(app.getPath("userData"), { recursive: true });
      await writeFile(getWorkspacePath(), serialized, "utf8");
      return { savedAt: new Date().toISOString() };
    },
  );

  ipcMain.handle(
    "model-ia:attachments:pick",
    async (event, projectId: string) => {
      const attachmentDirectory = getProjectAttachmentDirectory(projectId);
      const dialogOptions: OpenDialogOptions = {
        title: "Adjuntar referencias al proyecto",
        properties: ["openFile", "multiSelections"],
        filters: [
          {
            name: "Referencias de Model-IA",
            extensions: [
              "png",
              "jpg",
              "jpeg",
              "webp",
              "svg",
              "pdf",
              "step",
              "stp",
              "stl",
              "3mf",
              "obj",
              "dxf",
            ],
          },
        ],
      };
      const parentWindow = getParentWindow(event);
      const selection = parentWindow
        ? await dialog.showOpenDialog(parentWindow, dialogOptions)
        : await dialog.showOpenDialog(dialogOptions);

      if (selection.canceled) {
        return [];
      }

      await mkdir(attachmentDirectory, { recursive: true });
      const attachments = [];

      for (const sourcePath of selection.filePaths) {
        const extension = extname(sourcePath).toLowerCase();
        if (!ALLOWED_ATTACHMENT_EXTENSIONS.has(extension)) {
          continue;
        }

        const sourceStat = await stat(sourcePath);
        if (!sourceStat.isFile()) {
          continue;
        }

        const id = randomUUID();
        const storedName = `${id}${extension}`;
        await copyFile(sourcePath, join(attachmentDirectory, storedName));
        attachments.push({
          id,
          name: basename(sourcePath),
          size: sourceStat.size,
          mimeType: MIME_TYPES[extension] ?? "application/octet-stream",
          storedName,
          addedAt: new Date().toISOString(),
        });
      }

      return attachments;
    },
  );

  ipcMain.handle(
    "model-ia:attachments:remove",
    async (_event, projectId: string, storedName: string) => {
      try {
        await unlink(getStoredAttachmentPath(projectId, storedName));
        return true;
      } catch (error) {
        if (
          error instanceof Error &&
          "code" in error &&
          error.code === "ENOENT"
        ) {
          return true;
        }

        throw error;
      }
    },
  );

  ipcMain.handle(
    "model-ia:attachments:open",
    async (_event, projectId: string, storedName: string) => {
      const filePath = getStoredAttachmentPath(projectId, storedName);
      const fileStat = await stat(filePath);
      if (!fileStat.isFile()) {
        return false;
      }

      return (await shell.openPath(filePath)) === "";
    },
  );

  ipcMain.handle(
    "model-ia:projects:remove-data",
    async (_event, projectId: string) => {
      await rm(getProjectDirectory(projectId), {
        recursive: true,
        force: true,
      });
      return true;
    },
  );
};

const createWindow = (): void => {
  const mainWindow = new BrowserWindow({
    title: "Model-IA",
    width: 1600,
    height: 1000,
    minWidth: 1180,
    minHeight: 760,
    show: false,
    backgroundColor: "#071018",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    trafficLightPosition:
      process.platform === "darwin" ? { x: 18, y: 18 } : undefined,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: join(__dirname, "../preload/index.js"),
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) {
      void shell.openExternal(url);
    }

    return { action: "deny" };
  });

  const developmentUrl = process.env.ELECTRON_RENDERER_URL;

  if (developmentUrl) {
    void mainWindow.loadURL(developmentUrl);
  } else {
    void mainWindow.loadFile(
      join(__dirname, "../renderer/index.html"),
    );
  }
};

app.whenReady().then(() => {
  registerDesktopHandlers();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
