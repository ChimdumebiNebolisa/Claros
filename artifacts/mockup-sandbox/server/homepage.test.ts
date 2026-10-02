import { test, expect, type Page } from "@playwright/test";

const homepage = `https://${process.env.REPLIT_DEV_DOMAIN}/__mockup/preview/claros-reference/Homepage`;
async function installConnectionFixture(page: Page, denied = false) {
  await page.addInitScript(({ denied }) => {
    const state = {
      microphones: 0, stopped: 0, closed: 0, commands: [] as Record<string, unknown>[],
      channel: null as EventChannel | null, denied,
      emit(type: string, values: Record<string, unknown> = {}) {
        this.channel?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify({ type, ...values }) }));
      },
    };
    class EventChannel extends EventTarget {
      readyState = "connecting";
      send(data: string) { state.commands.push(JSON.parse(data)); }
      close() { this.readyState = "closed"; this.dispatchEvent(new Event("close")); }
    }
    class Peer extends EventTarget {
      iceGatheringState = "complete";
      connectionState = "new";
      localDescription: RTCSessionDescriptionInit | null = null;
      addTrack() {}
      addTransceiver() {}
      createDataChannel() { state.channel = new EventChannel(); return state.channel; }
      async createOffer() { return { type: "offer", sdp: "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n" }; }
      async setLocalDescription(value: RTCSessionDescriptionInit) { this.localDescription = value; }
      async setRemoteDescription() {
        queueMicrotask(() => {
          if (state.channel) {
            state.channel.readyState = "open";
            state.channel.dispatchEvent(new Event("open"));
          }
        });
      }
      close() { state.closed++; this.connectionState = "closed"; }
    }
    Object.defineProperty(window, "__demoFixture", { value: state });
    Object.defineProperty(window, "RTCPeerConnection", { value: Peer });
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      value: async () => {
        state.microphones++;
        if (state.denied) throw new DOMException("Denied by test", "NotAllowedError");
        const track = { enabled: true, stop() { state.stopped++; } };
        return { getAudioTracks: () => [track], getTracks: () => [track] };
      },
    });
  }, { denied });
  await page.route("**/api/claros-demo/status", route => route.fulfill({ json: { ready: true } }));
  await page.route("**/api/claros-demo/session", route => route.fulfill({
    status: 201, json: { sdp: "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n", leaseId: "t".repeat(43) },
  }));
  await page.route("**/api/claros-demo/end", route => route.fulfill({ status: 204 }));
}
async function emit(page: Page, type: string, values: Record<string, unknown> = {}) {
  await page.evaluate(({ type, values }) => {
    (window as unknown as { __demoFixture: { emit(type: string, values: Record<string, unknown>): void } }).__demoFixture.emit(type, values);
  }, { type, values });
}
async function stats(page: Page) {
  return page.evaluate(() => {
    const value = (window as unknown as { __demoFixture: { microphones: number; stopped: number; commands: Record<string, unknown>[] } }).__demoFixture;
    return { microphones: value.microphones, stopped: value.stopped, commands: value.commands };
  });
}

test("keeps the unavailable demo honest and the symbol layout within narrow viewports", async ({ page }) => {
  await installConnectionFixture(page);
  await page.route("**/api/claros-demo/status", route => route.fulfill({ json: { ready: false } }));
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(homepage);
  await expect(page.getByRole("heading", { name: /Think it\. Say it/ })).toBeVisible();
  expect((await stats(page)).microphones).toBe(0);
  await expect(page.locator(".cl-orbit-symbol")).toHaveCount(18);
  await page.evaluate(async () => { await document.fonts.ready; });
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const overlaps = await page.evaluate(() => {
      const textBounds: DOMRect[] = [];
      for (const element of document.querySelectorAll(".cl-hero h1, .cl-hero-copy")) {
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let node: Node | null;
        while ((node = walker.nextNode())) {
          const range = document.createRange();
          range.selectNodeContents(node);
          textBounds.push(...range.getClientRects());
        }
      }
      return [...document.querySelectorAll(".cl-orbit-symbol")].filter(symbol => {
        if (getComputedStyle(symbol).display === "none") return false;
        const box = symbol.getBoundingClientRect();
        return textBounds.some(text => box.left < text.right && box.right > text.left && box.top < text.bottom && box.bottom > text.top);
      }).map(symbol => symbol.textContent);
    });
    expect(overlaps, `Symbols must not cover hero text at ${width}px`).toEqual([]);
  }
  await page.getByRole("button", { name: "Talk it through" }).click();
  await expect(page.getByRole("alert")).toContainText("isn’t connected");
  await expect(page.locator(".cl-message")).toHaveCount(0);
  await expect(page.locator(".cl-audio-wave")).not.toHaveClass(/has-audio/);
  expect((await stats(page)).microphones).toBe(0);
  await page.getByRole("button", { name: "Close conversation" }).click();
  await expect(page.getByRole("region", { name: "Live question conversation" })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("processes live events, allows typed replies, mutes, and stops the microphone on close", async ({ page }) => {
  await installConnectionFixture(page);
  await page.goto(homepage);
  expect((await stats(page)).microphones).toBe(0);
  await page.getByRole("button", { name: "Talk it through" }).click();
  await expect(page.locator(".cl-session-status")).toHaveText("Listening");
  expect((await stats(page)).microphones).toBe(1);
  expect((await stats(page)).commands[0]).toEqual({ type: "response.create" });
  await page.getByRole("button", { name: "Mute microphone" }).click();
  await expect(page.getByRole("button", { name: "Unmute microphone" })).toBeVisible();
  await page.getByRole("button", { name: "Unmute microphone" }).click();
  await emit(page, "response.created");
  await emit(page, "response.output_audio_transcript.delta", { item_id: "reply1", delta: "What denominator could " });
  await emit(page, "response.output_audio_transcript.delta", { item_id: "reply1", delta: "both fractions use?" });
  await emit(page, "output_audio_buffer.started");
  await expect(page.locator(".cl-session-status")).toHaveText("Claros is speaking");
  await expect(page.locator(".cl-message.assistant")).toHaveText("What denominator could both fractions use?");
  await expect(page.locator(".cl-audio-wave")).toHaveClass(/has-audio/);
  await emit(page, "output_audio_buffer.stopped");
  await page.getByRole("textbox", { name: "Type a thought or question" }).fill("I think four.");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".cl-message.user")).toHaveText("I think four.");
  expect((await stats(page)).commands.filter(command => command.type === "response.create")).toHaveLength(2);
  await page.getByRole("button", { name: "End conversation" }).click();
  expect((await stats(page)).stopped).toBe(1);
});

test("typing remains usable after microphone permission is denied", async ({ page }) => {
  await installConnectionFixture(page, true);
  await page.goto(homepage);
  await page.getByRole("button", { name: "Talk it through" }).click();
  await expect(page.getByRole("alert")).toContainText("Microphone permission was blocked");
  await page.getByRole("button", { name: "Continue by typing" }).click();
  await expect(page.getByRole("textbox", { name: "Type a thought or question" })).toBeEnabled();
  await page.getByRole("textbox", { name: "Type a thought or question" }).fill("Can we use fourths?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".cl-message.user")).toHaveText("Can we use fourths?");
  expect((await stats(page)).microphones).toBe(1);
  await page.getByRole("button", { name: "End conversation" }).click();
});

test("closing while connecting prevents late microphone requests and sessions", async ({ page }) => {
  await installConnectionFixture(page);
  let sessions = 0;
  await page.route("**/api/claros-demo/status", async route => {
    await new Promise(resolve => setTimeout(resolve, 300));
    await route.fulfill({ json: { ready: true } }).catch(() => {});
  });
  await page.route("**/api/claros-demo/session", async route => {
    sessions++;
    await route.fulfill({ status: 500 });
  });
  await page.goto(homepage);
  await page.getByRole("button", { name: "Talk it through" }).click();
  await page.getByRole("button", { name: "Close conversation" }).click();
  await page.waitForTimeout(400);
  expect((await stats(page)).microphones).toBe(0);
  expect(sessions).toBe(0);
  await expect(page.locator(".cl-interaction")).toHaveCount(0);
});