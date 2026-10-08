// Opens a live WebSocket (/ws/dashboard or /ws/tourist), logs in with the first message,
// passes every event to `onEvent`, and reconnects after 3 s if the connection drops.
// Returns a function that closes it for good.

export type LiveStatus = { connected: boolean; mode: string | null };

export function openLiveSocket(
  path: "/ws/dashboard" | "/ws/tourist",
  token: string,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
  onStatus: (status: LiveStatus) => void,
): () => void {
  let socket: WebSocket;
  let retryTimer: number | undefined;
  let stopped = false;

  function connect() {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/api${path}`);
    // The token goes in the first message, not in the URL.
    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "ready") onStatus({ connected: true, mode: event.mode });
      else onEvent(event);
    };
    socket.onclose = () => {
      onStatus({ connected: false, mode: null });
      if (!stopped) retryTimer = window.setTimeout(connect, 3000);
    };
  }

  connect();
  return () => {
    stopped = true;
    window.clearTimeout(retryTimer);
    socket.close();
  };
}
