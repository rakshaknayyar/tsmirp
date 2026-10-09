// Safety assistant, shown as a short conversation. Each answer is picked from a fixed,
// hand-written list on the server (POST /assistant/query); it never makes answers up, and the
// emergency numbers 112 and 1363 are always shown. The conversation is not stored anywhere.

import { Phone, Send } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";
import { Notice, Panel } from "../shared/ui";

type AssistantReply = {
  topic: string | null;
  title: string | null;
  answer: string;
  emergency: string;
  language: string;
  note: string;
};

type Exchange = { question: string; reply: AssistantReply };

const SUGGESTIONS = [
  "My passport is lost",
  "Mera phone chori ho gaya",
  "Someone is following me",
  "How does SOS work?",
  "Who can see my location?",
];

export default function AssistantPanel({ token }: { token: string }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [history.length]);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (trimmed.length < 2) return;
    setError(null);
    setBusy(true);
    try {
      const reply = await apiRequest<AssistantReply>("POST", "/assistant/query", {
        token,
        body: { question: trimmed },
      });
      setHistory((list) => [...list, { question: trimmed, reply }]);
      setQuestion("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  return (
    <Panel
      title="Safety assistant"
      description="Ask in English, Hindi or romanised Hindi. Answers come from a fixed list written for visitors to Jaipur."
    >
      <div className="stack">
        {history.length === 0 ? (
          <div className="stack">
            <p className="muted">Try one of these, or type your own question:</p>
            <div className="chips">
              {SUGGESTIONS.map((text) => (
                <button key={text} type="button" className="chip" onClick={() => void ask(text)}>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat" aria-live="polite">
            {history.map(({ question: asked, reply }, index) => (
              <div className="chat" key={index}>
                <p className="chat-msg chat-msg-user">{asked}</p>
                <div className="chat-msg chat-msg-bot">
                  {reply.title && <strong>{reply.title}</strong>}
                  <p>{reply.answer}</p>
                  <p className="chat-emergency">
                    <Phone aria-hidden="true" />
                    {reply.emergency}
                  </p>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}

        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}

        <form className="chat-compose" onSubmit={handleSubmit}>
          <label className="visually-hidden" htmlFor={`${id}-question`}>
            Your question
          </label>
          <input
            id={`${id}-question`}
            className="input"
            placeholder="Ask a safety question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || question.trim().length < 2}>
            <Send aria-hidden="true" />
            Ask
          </button>
        </form>
        <p className="small muted">
          General guidance only, not legal or medical advice. Your questions are not saved.
        </p>
      </div>
    </Panel>
  );
}
