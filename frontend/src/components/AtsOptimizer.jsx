import { useMemo, useState } from "react";
import { Github, Linkedin } from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function toEditable(data) {
  return {
    name: "",
    contact: "",
    professional_summary: data?.optimized_resume?.professional_summary || "",
    experience: (data?.optimized_resume?.experience || []).map((exp) => ({
      title: exp.title || "",
      company: exp.company || "",
      period: exp.period || "",
      bullets: Array.isArray(exp.bullets) ? exp.bullets : [],
    })),
  };
}

export default function AtsOptimizer() {
  const [pdfFile, setPdfFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [editable, setEditable] = useState(null);

  const canSubmit = useMemo(() => pdfFile && jobDescription.trim(), [pdfFile, jobDescription]);

  async function handleOptimize(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setEditable(null);

    if (!canSubmit) {
      setError("Envie um PDF e preencha a descrição da vaga.");
      return;
    }

    const formData = new FormData();
    formData.append("resume_pdf", pdfFile);
    formData.append("job_description", jobDescription);

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/optimize-cv`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Falha ao otimizar o currículo.");
      }

      setResult(data);
      setEditable(toEditable(data));
    } catch (err) {
      setError(err.message || "Erro inesperado.");
    } finally {
      setLoading(false);
    }
  }

  function updateExperienceField(index, field, value) {
    setEditable((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      next.experience[index][field] = value;
      return next;
    });
  }

  function updateBullet(experienceIndex, bulletIndex, value) {
    setEditable((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      next.experience[experienceIndex].bullets[bulletIndex] = value;
      return next;
    });
  }

  function addBullet(experienceIndex) {
    setEditable((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      next.experience[experienceIndex].bullets.push("");
      return next;
    });
  }

  async function downloadPdf() {
    if (!editable) return;

    const payload = {
      name: editable.name || "Candidato",
      contact: editable.contact || "",
      optimized_resume: {
        professional_summary: editable.professional_summary,
        experience: editable.experience,
      },
    };

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/export-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Falha ao exportar PDF.");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "curriculo_ats.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Erro ao baixar PDF.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <header className="header">
        <div className="header-content">
          <div className="header-brand">
            <h1 className="header-title">ATS Optimizer</h1>
          </div>
          <div className="header-creator">
            <span className="creator-label">Created by Ivan Lana</span>
            <div className="social-links">
              <a 
                href="https://github.com/Iv4nLanna" 
                target="_blank" 
                rel="noopener noreferrer"
                className="social-icon-link github"
                title="GitHub"
              >
                <Github size={20} />
              </a>
              <a 
                href="https://www.linkedin.com/in/ivan-lana/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="social-icon-link linkedin"
                title="LinkedIn"
              >
                <Linkedin size={20} />
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="page">
        <form className="form" onSubmit={handleOptimize}>
          <label>
            PDF do currículo
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
            />
          </label>

          <label>
            Texto da vaga
            <textarea
              rows={8}
              value={jobDescription}
              onChange={(event) => setJobDescription(event.target.value)}
              placeholder="Cole aqui a descrição da vaga"
            />
          </label>

          <button type="submit" disabled={loading || !canSubmit}>
            {loading ? "Processando..." : "Otimizar"}
          </button>
        </form>

        {error && <p className="error">{error}</p>}

        {result && editable && (
          <section className="results">
          <div className="col">
            <h2>Original (extraído do PDF)</h2>
            <textarea readOnly rows={30} value={result.original_resume_text || ""} />
          </div>

          <div className="col">
            <h2>Otimizado (editável)</h2>

            <label>
              Nome
              <input
                type="text"
                value={editable.name}
                onChange={(event) =>
                  setEditable((prev) => ({ ...prev, name: event.target.value }))
                }
              />
            </label>

            <label>
              Contato
              <input
                type="text"
                value={editable.contact}
                onChange={(event) =>
                  setEditable((prev) => ({ ...prev, contact: event.target.value }))
                }
                placeholder="Cidade | email | telefone | LinkedIn"
              />
            </label>

            <label>
              Resumo Profissional
              <textarea
                rows={7}
                value={editable.professional_summary}
                onChange={(event) =>
                  setEditable((prev) => ({
                    ...prev,
                    professional_summary: event.target.value,
                  }))
                }
              />
            </label>

            <h3>Experiência</h3>
            {editable.experience.map((exp, expIndex) => (
              <article key={`${exp.title}-${expIndex}`} className="experience-card">
                <input
                  type="text"
                  value={exp.title}
                  onChange={(event) =>
                    updateExperienceField(expIndex, "title", event.target.value)
                  }
                  placeholder="Cargo"
                />
                <input
                  type="text"
                  value={exp.company}
                  onChange={(event) =>
                    updateExperienceField(expIndex, "company", event.target.value)
                  }
                  placeholder="Empresa"
                />
                <input
                  type="text"
                  value={exp.period}
                  onChange={(event) =>
                    updateExperienceField(expIndex, "period", event.target.value)
                  }
                  placeholder="Período"
                />

                {exp.bullets.map((bullet, bulletIndex) => (
                  <textarea
                    key={`${expIndex}-${bulletIndex}`}
                    rows={2}
                    value={bullet}
                    onChange={(event) =>
                      updateBullet(expIndex, bulletIndex, event.target.value)
                    }
                    placeholder="Bullet"
                  />
                ))}

                <button type="button" className="secondary" onClick={() => addBullet(expIndex)}>
                  Adicionar bullet
                </button>
              </article>
            ))}

            <div className="meta">
              <p>
                <strong>Hard Skills:</strong> {(result.hard_skills || []).join(", ")}
              </p>
              <p>
                <strong>Verbos:</strong> {(result.action_verbs || []).join(", ")}
              </p>
              {!!result.warnings?.length && (
                <p>
                  <strong>Warnings:</strong> {result.warnings.join(" | ")}
                </p>
              )}
            </div>

            <button type="button" onClick={downloadPdf} disabled={loading}>
              Baixar PDF ATS
            </button>
          </div>
        </section>
        )}
      </main>
    </>
  );
}
