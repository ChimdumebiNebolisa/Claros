import { readFileSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

import { render } from "../.ssr/entry-server.js"

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const landingPath = path.resolve(scriptDirectory, "../../frontend/landing.html")
const rootMarker = '<div id="root"></div>'
const html = readFileSync(landingPath, "utf8")

if (!html.includes(rootMarker)) {
  throw new Error("Built landing root marker was not found")
}

writeFileSync(
  landingPath,
  html.replace(rootMarker, `<div id="root">${render()}</div>`),
  "utf8"
)
