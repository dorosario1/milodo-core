import { exec } from "child_process";
import http from "http";

const SECRET = "milodo-secret";

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("MILODO API OK");
    return;
  }

  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (req.url.startsWith("/run/") && req.headers["x-api-key"] !== SECRET) {
    res.writeHead(403, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "unauthorized" }));
    return;
  }

  if (req.method === "GET" && req.url === "/run/test") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "API connected" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/build") {
    console.log("[RUN] build requested");
    exec("docker compose build", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "build triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/test") {
    console.log("[RUN] test requested");
    exec("docker compose ps", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "test triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/deploy_site") {
    console.log("[RUN] deploy_site requested");
    exec("docker compose up -d --remove-orphans", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "deploy triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/backup_db") {
    console.log("[RUN] backup_db requested");
    exec("docker exec db pg_dump -U milodo milodo > backup.sql", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "backup_db triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/restart_api") {
    console.log("[RUN] restart_api requested");
    exec("docker compose restart api", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "restart_api triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/clean_docker") {
    console.log("[RUN] clean_docker requested");
    exec("docker system prune -f", (error, stdout, stderr) => {
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      if (error) console.error(error);
    });

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "clean_docker triggered" }));
    return;
  }

  if (req.method === "POST" && req.url === "/run/command") {
    let body = "";

    req.on("data", (chunk) => {
      body += chunk;
    });

    req.on("end", () => {
      const commands = {
        deploy_site: "docker compose up -d",
        build: "docker compose build",
        test: "docker compose ps"
      };

      try {
        const payload = JSON.parse(body);
        const command = commands[payload.command];

        if (!command) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ status: "unknown command" }));
          return;
        }

        console.log(`[RUN] command requested: ${payload.command}`);
        exec(command, (error, stdout, stderr) => {
          if (stdout) console.log(stdout);
          if (stderr) console.error(stderr);
          if (error) console.error(error);
        });

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: `${payload.command} triggered` }));
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "invalid json" }));
      }
    });

    return;
  }

  if (req.method === "POST" && req.url === "/run/ai") {
    let body = "";

    req.on("data", (chunk) => {
      body += chunk;
    });

    req.on("end", async () => {
      try {
        const payload = JSON.parse(body);
        const text = String(payload.text || "").toLowerCase();
        let action = "";
        let command = "";

        try {
          if (!process.env.OPENAI_API_KEY) {
            throw new Error("missing OpenAI API key");
          }

          const openaiResponse = await fetch("https://api.openai.com/v1/responses", {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              model: process.env.OPENAI_MODEL || "gpt-5.2",
              instructions: "Map the user intent to exactly one action. Only allowed actions: deploy_site, build, test. Never invent new actions. If unsure, return \"blocked\". Return only the action string. Examples: \"deploy\" -> deploy_site; \"build\" -> build; \"test\" -> test.",
              input: text
            })
          });

          if (!openaiResponse.ok) {
            throw new Error("OpenAI API failed");
          }

          const openaiData = await openaiResponse.json();
          const mappedAction =
            openaiData.output?.[0]?.content?.[0]?.text || "blocked";
          action = ["deploy_site", "build", "test"].includes(mappedAction) ? mappedAction : "blocked";
        } catch {
          if (text.includes("deploy")) {
            action = "deploy_site";
          } else if (text.includes("build")) {
            action = "build";
          } else if (text.includes("test")) {
            action = "test";
          } else {
            action = "blocked";
          }
        }

        if (action === "deploy_site") {
          action = "deploy_site";
          command = "docker compose up -d";
        } else if (action === "build") {
          action = "build";
          command = "docker compose build";
        } else if (action === "test") {
          action = "test";
          command = "docker compose ps";
        }

        if (!command) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ action: "blocked" }));
          return;
        }

        console.log(`[RUN] ai mapped to: ${action}`);
        exec(command, (error, stdout, stderr) => {
          if (stdout) console.log(stdout);
          if (stderr) console.error(stderr);
          if (error) console.error(error);
        });

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ action }));
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ action: "invalid_json" }));
      }
    });

    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain" });
  res.end("Not found");
});

server.listen(3000, () => {
  console.log("MILODO API listening on port 3000");
});
