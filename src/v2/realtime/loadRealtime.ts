export async function loadRealtimeAdapter() {
  return import("./realtime-adapter");
}

export async function loadOpenAIRealtimeAdapter() {
  return import("./openai-realtime-adapter");
}
