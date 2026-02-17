import { useMemo, useRef, useState } from "react";
import { Briefcase, Check, Download, FileText, Github, Linkedin, Sparkles } from "lucide-react";

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
  const fileInputRef = useRef(null);
  const [pdfFile, setPdfFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [editable, setEditable] = useState(null);
  const [activeTab, setActiveTab] = useState("input");
  const [dragActive, setDragActive] = useState(false);

  const canSubmit = useMemo(() => pdfFile && jobDescription.trim(), [pdfFile, jobDescription]);

  const handleDrag = (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);

    const files = event.dataTransfer.files;
    if (files && files[0]?.type === "application/pdf") {
      setPdfFile(files[0]);
      setError("");
    } else {
      setError("Formato invalido. Selecione um arquivo PDF.");
    }
  };

  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  async function handleOptimize(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setEditable(null);

    if (!canSubmit) {
      setError("Envie um PDF e preencha a descricao da vaga.");
      return;
    }

    const formData = new FormData();
    formData.append("resume_pdf", pdfFile);
    formData.append("job_description", jobDescription);
    formData.append("captcha_token", captchaToken.trim());

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/optimize-cv`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Falha ao otimizar o curriculo.");
      }

      setResult(data);
      setEditable(toEditable(data));
      setActiveTab("output");
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

  const jobDescCharCount = jobDescription.length;
  const maxChars = 5000;

  return (
    <>
      <header className="header">
        <div className="header-content">
          <div className="header-brand">
            <div className="logo">
              <span className="logo-text">ATS</span>
            </div>
            <div>
              <h1 className="header-title">
                ATS
                <span className="header-subtitle">Optimizer</span>
              </h1>
            </div>
          </div>
          <div className="header-creator">
            <span className="creator-label">by Ivan Lana</span>
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

      <main className="page" style={{ gridTemplateColumns: "1fr" }}>
        <div className="content-area">
          {result && (
            <div className="tabs-nav">
              <button
                className={`tab-button ${activeTab === "input" ? "active" : ""}`}
                onClick={() => setActiveTab("input")}
              >
                Comparacao
              </button>
              <button
                className={`tab-button ${activeTab === "output" ? "active" : ""}`}
                onClick={() => setActiveTab("output")}
              >
                Editar
              </button>
            </div>
          )}

          <div className="tab-content">
            {activeTab === "input" && !result && (
              <form className="form" onSubmit={handleOptimize}>
                <div className="form-group">
                  <label className="form-label">
                    <div style={{ display: "flex", gap: "var(--spacing-md)", alignItems: "center" }}>
                      <FileText size={20} color="var(--color-accent-red)" />
                      PDF do Curriculo
                    </div>
                  </label>
                  <div
                    className={`file-upload ${dragActive ? "drag-active" : ""}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={openFilePicker}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openFilePicker();
                      }
                    }}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="file-upload-content">
                      <div className="file-upload-icon">PDF</div>
                      <div className="file-upload-text">Arraste seu PDF aqui ou clique para selecionar</div>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/pdf"
                      onChange={(event) => {
                        if (event.target.files?.[0]) {
                          setPdfFile(event.target.files[0]);
                          setError("");
                        }
                      }}
                    />
                  </div>
                  {pdfFile && (
                    <div className="file-name">
                      <Check size={16} style={{ color: "var(--color-success)" }} />
                      {pdfFile.name}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label">
                    <div style={{ display: "flex", gap: "var(--spacing-md)", alignItems: "center" }}>
                      <Briefcase size={20} color="var(--color-accent-red)" />
                      Descricao da Vaga
                    </div>
                  </label>
                  <textarea
                    rows={10}
                    value={jobDescription}
                    onChange={(event) => setJobDescription(event.target.value)}
                    placeholder="Cole aqui a descricao completa da vaga"
                    maxLength={maxChars}
                  />
                  <div className={`char-counter ${jobDescCharCount > maxChars * 0.8 ? "warning" : ""}`}>
                    {jobDescCharCount} / {maxChars} caracteres
                  </div>
                </div>

                <div className="form-group">
                  <label>
                    Captcha Token (opcional)
                    <input
                      type="text"
                      value={captchaToken}
                      onChange={(event) => setCaptchaToken(event.target.value)}
                      placeholder="Preencha apenas se captcha estiver habilitado"
                    />
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={loading || !canSubmit}
                  style={{
                    display: "flex",
                    gap: "var(--spacing-md)",
                    justifyContent: "center",
                    alignItems: "center",
                  }}
                >
                  <Sparkles size={18} />
                  {loading ? "Processando..." : "Otimizar Curriculo"}
                </button>
              </form>
            )}

            {activeTab === "input" && result && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-xl)", alignItems: "start" }}>
                <div className="col">
                  <h2>Original (PDF)</h2>
                  <textarea readOnly rows={30} value={result.original_resume_text || ""} style={{ color: "var(--color-text-muted)" }} />
                </div>

                <div className="col">
                  <h2>Otimizado</h2>
                  <textarea
                    readOnly
                    rows={30}
                    value={
                      editable
                        ? `${editable.name}\n${editable.contact}\n\n${editable.professional_summary}\n\n${editable.experience
                            .map((exp) => `${exp.title} - ${exp.company} (${exp.period})\n${exp.bullets.join("\n")}`)
                            .join("\n\n")}`
                        : ""
                    }
                  />
                </div>
              </div>
            )}

            {activeTab === "output" && result && editable && (
              <div style={{ display: "grid", gap: "var(--spacing-xl)" }}>
                <div className="col">
                  <h2>Editar Curriculo Otimizado</h2>

                  <div className="form-group">
                    <label>
                      Nome Completo
                      <input
                        type="text"
                        value={editable.name}
                        onChange={(event) => setEditable((prev) => ({ ...prev, name: event.target.value }))}
                        placeholder="Seu nome"
                      />
                    </label>
                  </div>

                  <div className="form-group">
                    <label>
                      Contato
                      <input
                        type="text"
                        value={editable.contact}
                        onChange={(event) => setEditable((prev) => ({ ...prev, contact: event.target.value }))}
                        placeholder="Cidade | email | telefone | LinkedIn"
                      />
                    </label>
                  </div>

                  <div className="form-group">
                    <label>
                      Resumo Profissional
                      <textarea
                        rows={8}
                        value={editable.professional_summary}
                        onChange={(event) =>
                          setEditable((prev) => ({
                            ...prev,
                            professional_summary: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>

                  <h3>Experiencia Profissional</h3>
                  {editable.experience.map((exp, expIndex) => (
                    <article key={`${exp.title}-${expIndex}`} className="experience-card">
                      <input
                        type="text"
                        value={exp.title}
                        onChange={(event) => updateExperienceField(expIndex, "title", event.target.value)}
                        placeholder="Cargo"
                      />
                      <input
                        type="text"
                        value={exp.company}
                        onChange={(event) => updateExperienceField(expIndex, "company", event.target.value)}
                        placeholder="Empresa"
                      />
                      <input
                        type="text"
                        value={exp.period}
                        onChange={(event) => updateExperienceField(expIndex, "period", event.target.value)}
                        placeholder="Periodo (ex: Jan 2020 - Dez 2022)"
                      />

                      {exp.bullets.map((bullet, bulletIndex) => (
                        <textarea
                          key={`${expIndex}-${bulletIndex}`}
                          rows={2}
                          value={bullet}
                          onChange={(event) => updateBullet(expIndex, bulletIndex, event.target.value)}
                          placeholder="Descreva sua contribuicao"
                        />
                      ))}

                      <button type="button" className="secondary" onClick={() => addBullet(expIndex)}>
                        + Adicionar Bullet Point
                      </button>
                    </article>
                  ))}

                  <button
                    type="button"
                    onClick={downloadPdf}
                    disabled={loading}
                    style={{
                      display: "flex",
                      gap: "var(--spacing-md)",
                      justifyContent: "center",
                      alignItems: "center",
                      width: "100%",
                    }}
                  >
                    <Download size={18} />
                    {loading ? "Gerando PDF..." : "Baixar PDF Otimizado"}
                  </button>
                </div>
              </div>
            )}

            {loading && (
              <div className="col" style={{ background: "var(--color-surface)", border: "none" }}>
                <h2>Processando seu curriculo...</h2>
              </div>
            )}

            {error && <p className="error">{error}</p>}
          </div>
        </div>
      </main>
    </>
  );
}
