import React, { useMemo, useRef, useState } from "react";
import { 
  Github, 
  Linkedin, 
  FileText, 
  Briefcase, 
  Sparkles,
  Download,
  Check
} from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const AUTH_TOKEN_KEY = "ats_auth_token";

function withAuth(headers = {}, token = "") {
  if (!token) return headers;
  return { ...headers, Authorization: `Bearer ${token}` };
}

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

const Toast = ({ type, title, message, onClose }) => {
  React.useEffect(() => {
    const timer = setTimeout(onClose, 5000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const icons = { success: "✓", error: "✕", warning: "!" };

  return (
    <div className={`toast ${type}`}>
      <span className="toast-icon">{icons[type]}</span>
      <div className="toast-content">
        <div className="toast-title">{title}</div>
        <div className="toast-message">{message}</div>
      </div>
    </div>
  );
};

const ProgressStep = ({ step, completed, active }) => {
  const steps = [
    { num: 1, title: "Upload PDF", icon: "📄" },
    { num: 2, title: "Preencher Vaga", icon: "📋" },
    { num: 3, title: "Otimizar", icon: "✨" },
    { num: 4, title: "Resultado", icon: "🎉" },
  ];

  const s = steps[step];

  return (
    <div className={`progress-step ${completed ? "completed" : ""} ${active ? "active" : ""}`}>
      <div className="step-icon">
        {completed ? <Check size={20} /> : s.icon}
      </div>
      <div className="step-content">
        <div className="step-label">Etapa {s.num}</div>
        <div className="step-title">{s.title}</div>
      </div>
    </div>
  );
};

const SkeletonLoader = () => (
  <div style={{ display: "grid", gap: "var(--spacing-lg)" }}>
    <div className="skeleton skeleton-box"></div>
    <div className="skeleton skeleton-text"></div>
    <div className="skeleton skeleton-text short"></div>
    <div style={{ display: "grid", gap: "var(--spacing-sm)" }}>
      <div className="skeleton skeleton-line"></div>
      <div className="skeleton skeleton-line"></div>
      <div className="skeleton skeleton-line"></div>
    </div>
  </div>
);

export default function AtsOptimizer() {
  const fileInputRef = useRef(null);
  const [pdfFile, setPdfFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [editable, setEditable] = useState(null);
  const [activeTab, setActiveTab] = useState("input");
  const [toasts, setToasts] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY) || "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginCaptchaToken, setLoginCaptchaToken] = useState("");
  const [optimizeCaptchaToken, setOptimizeCaptchaToken] = useState("");

  const canSubmit = useMemo(() => pdfFile && jobDescription.trim(), [pdfFile, jobDescription]);

  // Progress calculation
  const currentStep = useMemo(() => {
    if (result && editable) return 3;
    if (jobDescription.trim()) return 1;
    if (pdfFile) return 0;
    return -1;
  }, [pdfFile, jobDescription, result, editable]);

  const addToast = (type, title, message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, title, message }]);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Drag and drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]?.type === "application/pdf") {
      setPdfFile(files[0]);
      addToast("success", "Arquivo Enviado", `${files[0].name} carregado com sucesso!`);
    } else {
      addToast("error", "Formato Inválido", "Por favor, selecione um arquivo PDF");
    }
  };

  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  async function handleLogin(event) {
    event.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      addToast("error", "Login inválido", "Preencha usuário e senha.");
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
          captcha_token: loginCaptchaToken.trim() || null,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Falha no login.");
      }

      localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
      setAuthToken(data.access_token);
      addToast("success", "Login efetuado", "Sessão autenticada com sucesso.");
    } catch (err) {
      setError(err.message || "Erro de autenticação.");
      addToast("error", "Falha no login", err.message || "Erro de autenticação.");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setAuthToken("");
    setResult(null);
    setEditable(null);
    addToast("warning", "Sessão encerrada", "Você saiu da sessão.");
  }

  async function handleOptimize(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setEditable(null);

    if (!canSubmit) {
      setError("Envie um PDF e preencha a descrição da vaga.");
      addToast("error", "Erro", "Preencha todos os campos obrigatórios");
      return;
    }

    const formData = new FormData();
    formData.append("resume_pdf", pdfFile);
    formData.append("job_description", jobDescription);
    formData.append("captcha_token", optimizeCaptchaToken.trim());

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/optimize-cv`, {
        method: "POST",
        headers: withAuth({}, authToken),
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          handleLogout();
        }
        throw new Error(data.detail || "Falha ao otimizar o currículo.");
      }

      setResult(data);
      setEditable(toEditable(data));
      setActiveTab("output");
      addToast("success", "Otimização Concluída!", "Seu currículo foi otimizado com sucesso");
    } catch (err) {
      setError(err.message || "Erro inesperado.");
      addToast("error", "Erro na Otimização", err.message);
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
        headers: withAuth({
          "Content-Type": "application/json",
        }, authToken),
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        if (response.status === 401) {
          handleLogout();
        }
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
      addToast("success", "Download Iniciado", "Seu PDF foi baixado com sucesso!");
    } catch (err) {
      setError(err.message || "Erro ao baixar PDF.");
      addToast("error", "Erro no Download", err.message);
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
              <span className="logo-text">⚡</span>
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
            {authToken && (
              <button
                type="button"
                className="secondary"
                onClick={handleLogout}
                style={{ padding: "6px 10px", fontSize: "12px" }}
              >
                Sair
              </button>
            )}
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
        {/* Progress Sidebar */}
        <div className="progress-sidebar">
          <ProgressStep step={0} completed={currentStep >= 0} active={currentStep === 0} />
          <ProgressStep step={1} completed={currentStep >= 1} active={currentStep === 1} />
          <ProgressStep step={2} completed={currentStep >= 2} active={currentStep === 2} />
          <ProgressStep step={3} completed={currentStep >= 3} active={currentStep === 3} />
        </div>

        {/* Main Content Area */}
        <div className="content-area">
          {/* Tabs Navigation */}
          {authToken && result && (
            <div className="tabs-nav">
              <button 
                className={`tab-button ${activeTab === "input" ? "active" : ""}`}
                onClick={() => setActiveTab("input")}
              >
                Comparação
              </button>
              <button 
                className={`tab-button ${activeTab === "output" ? "active" : ""}`}
                onClick={() => setActiveTab("output")}
              >
                Editar
              </button>
            </div>
          )}

          {/* Tab Content */}
          <div className="tab-content">
            {!authToken && (
              <div className="col">
                <h2>Autenticacao</h2>
                <form className="form" onSubmit={handleLogin}>
                  <div className="form-group">
                    <label>
                      Usuario
                      <input
                        type="text"
                        value={username}
                        onChange={(event) => setUsername(event.target.value)}
                        placeholder="Seu usuario"
                      />
                    </label>
                  </div>
                  <div className="form-group">
                    <label>
                      Senha
                      <input
                        type="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        placeholder="Sua senha"
                      />
                    </label>
                  </div>
                  <div className="form-group">
                    <label>
                      Captcha Token (opcional)
                      <input
                        type="text"
                        value={loginCaptchaToken}
                        onChange={(event) => setLoginCaptchaToken(event.target.value)}
                        placeholder="Preencha apenas se captcha estiver habilitado"
                      />
                    </label>
                  </div>
                  <button type="submit" disabled={loading}>
                    {loading ? "Entrando..." : "Entrar"}
                  </button>
                </form>
              </div>
            )}

            {/* INPUT TAB - Form */}
            {authToken && activeTab === "input" && !result && (
              <form className="form" onSubmit={handleOptimize}>
                <div className="form-group">
                  <label className="form-label">
                    <div style={{ display: "flex", gap: "var(--spacing-md)", alignItems: "center" }}>
                      <FileText size={20} color="var(--color-accent-red)" />
                      PDF do Currículo
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
                      <div className="file-upload-icon">📁</div>
                      <div className="file-upload-text">
                        Arraste seu PDF aqui ou clique para selecionar
                      </div>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/pdf"
                      onChange={(event) => {
                        if (event.target.files?.[0]) {
                          setPdfFile(event.target.files[0]);
                          addToast("success", "Arquivo Enviado", `${event.target.files[0].name} carregado!`);
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
                      Descrição da Vaga
                    </div>
                  </label>
                  <textarea
                    rows={10}
                    value={jobDescription}
                    onChange={(event) => setJobDescription(event.target.value)}
                    placeholder="Cole aqui a descrição completa da vaga que deseja aplicar"
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
                      value={optimizeCaptchaToken}
                      onChange={(event) => setOptimizeCaptchaToken(event.target.value)}
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
                    alignItems: "center"
                  }}
                >
                  <Sparkles size={18} />
                  {loading ? "Processando..." : "Otimizar Currículo"}
                </button>
              </form>
            )}

            {/* COMPARAÇÃO - Original vs Otimizado */}
            {authToken && activeTab === "input" && result && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-xl)", alignItems: "start" }}>
                <div className="col">
                  <h2>📄 Original (PDF)</h2>
                  <textarea 
                    readOnly 
                    rows={30} 
                    value={result.original_resume_text || ""} 
                    style={{ color: "var(--color-text-muted)" }}
                  />
                </div>

                <div className="col">
                  <h2 style={{ display: "flex", gap: "var(--spacing-md)", alignItems: "center" }}>
                    ✨ Otimizado
                    <div className="improvement-badge">
                      {(result.hard_skills?.length || 0) + (result.action_verbs?.length || 0)}
                    </div>
                  </h2>
                  <textarea 
                    readOnly 
                    rows={30} 
                    value={
                      editable ? 
                      `${editable.name}\n${editable.contact}\n\n${editable.professional_summary}\n\n${
                        editable.experience
                          .map(exp => `${exp.title} - ${exp.company} (${exp.period})\n${exp.bullets.join("\n")}`)
                          .join("\n\n")
                      }` 
                      : ""
                    }
                  />
                </div>
              </div>
            )}

            {/* OUTPUT TAB - Edit */}
            {authToken && activeTab === "output" && result && editable && (
              <div style={{ display: "grid", gap: "var(--spacing-xl)" }}>
                <div className="col">
                  <h2>✏️ Editar Currículo Otimizado</h2>

                  <div className="form-group">
                    <label>
                      Nome Completo
                      <input
                        type="text"
                        value={editable.name}
                        onChange={(event) =>
                          setEditable((prev) => ({ ...prev, name: event.target.value }))
                        }
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
                        onChange={(event) =>
                          setEditable((prev) => ({ ...prev, contact: event.target.value }))
                        }
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

                  <h3>Experiência Profissional</h3>
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
                        placeholder="Período (ex: Jan 2020 - Dez 2022)"
                      />

                      {exp.bullets.map((bullet, bulletIndex) => (
                        <textarea
                          key={`${expIndex}-${bulletIndex}`}
                          rows={2}
                          value={bullet}
                          onChange={(event) =>
                            updateBullet(expIndex, bulletIndex, event.target.value)
                          }
                          placeholder="Descreva seu achievement/responsabilidade"
                        />
                      ))}

                      <button 
                        type="button" 
                        className="secondary" 
                        onClick={() => addBullet(expIndex)}
                      >
                        + Adicionar Bullet Point
                      </button>
                    </article>
                  ))}

                  {/* Meta Information with Badges */}
                  <div className="meta">
                    <div className="meta-card skills">
                      <h4 className="meta-title">💡 Hard Skills Encontradas</h4>
                      <div className="meta-content">
                        {(result.hard_skills || []).length > 0 ? (
                          (result.hard_skills || []).map((skill, idx) => (
                            <span key={idx} className="badge">{skill}</span>
                          ))
                        ) : (
                          <p style={{ color: "var(--color-text-muted)", margin: 0 }}>Nenhuma skill encontrada</p>
                        )}
                      </div>
                    </div>

                    <div className="meta-card verbs">
                      <h4 className="meta-title">🎯 Action Verbs Utilizados</h4>
                      <div className="meta-content">
                        {(result.action_verbs || []).length > 0 ? (
                          (result.action_verbs || []).map((verb, idx) => (
                            <span key={idx} className="badge">{verb}</span>
                          ))
                        ) : (
                          <p style={{ color: "var(--color-text-muted)", margin: 0 }}>Nenhum verbo encontrado</p>
                        )}
                      </div>
                    </div>

                    {!!result.warnings?.length && (
                      <div className="meta-card warnings">
                        <h4 className="meta-title">⚠️ Avisos e Melhorias</h4>
                        <div style={{ display: "grid", gap: "var(--spacing-sm)" }}>
                          {result.warnings.map((warning, idx) => (
                            <p key={idx} style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>
                              • {warning}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <button 
                    type="button" 
                    onClick={downloadPdf} 
                    disabled={loading}
                    style={{
                      display: "flex",
                      gap: "var(--spacing-md)",
                      justifyContent: "center",
                      alignItems: "center",
                      width: "100%"
                    }}
                  >
                    <Download size={18} />
                    {loading ? "Gerando PDF..." : "Baixar PDF Otimizado"}
                  </button>
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="col" style={{ background: "var(--color-surface)", border: "none" }}>
                <h2>⏳ Processando seu currículo...</h2>
                <SkeletonLoader />
              </div>
            )}

            {/* Error State */}
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      </main>

      {/* Toast Container */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            type={toast.type}
            title={toast.title}
            message={toast.message}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </>
  );
}
