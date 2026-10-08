// Safety assistant: the tourist types a question (English, Hindi or romanised Hindi) and gets
// an answer picked from a fixed, hand-written list (POST /assistant/query). It never makes up
// answers, and the emergency numbers 112 and 1363 are always shown.

import { useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";

type AssistantReply = {
  topic: string | null;
  title: string | null;
  answer: string;
  emergency: string;
  language: string;
  note: string;
};

const EXAMPLES = ["My passport is lost", "Mera phone chori ho gaya", "How does SOS work?"];

export default function AssistantPanel({ token }: { token: string }) {
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState<AssistantReply | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(text: string) {
    setError(null);
    try {
      const result = await apiRequest<AssistantReply>("POST", "/assistant/query", {
        token,
        body: { question: text },
      });
      setReply(result);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length >= 2) ask(question);
  }

  return (
    <section>
      <h2>Safety assistant</h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, maxWidth: 480 }}>
        <input
          style={{ flex: 1, minWidth: 0 }}
          placeholder="Ask a safety question (English or Hindi)"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
        />
        <button type="submit">Ask</button>
      </form>
      <p style={{ fontSize: 13 }}>
        Try:{" "}
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              setQuestion(example);
              ask(example);
            }}
            style={{ marginRight: 4 }}
          >
            {example}
          </button>
        ))}
      </p>
      {error && <p role="alert">{error}</p>}
      {reply && (
        <div role="status" style={{ border: "1px solid #ccc", borderRadius: 6, padding: 8 }}>
          {reply.title && <strong>{reply.title}</strong>}
          <p style={{ margin: "4px 0" }}>{reply.answer}</p>
          <p style={{ margin: "4px 0", fontWeight: "bold", color: "#c62828" }}>
            {reply.emergency}
          </p>
          <p style={{ margin: 0, fontSize: 12 }}>{reply.note}</p>
        </div>
      )}
    </section>
  );
}
