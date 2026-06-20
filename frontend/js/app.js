// Фронт отдаётся тем же приложением FastAPI, поэтому API дергаем относительным
// путём. Если фронт хостится отдельно — пропиши сюда базовый URL бэкенда.
const API_BASE = "";

const form = document.getElementById("contact-form");
const submitBtn = document.getElementById("submit-btn");
const resultBox = document.getElementById("result");
const resultText = document.getElementById("result-text");
const resultAnalysis = document.getElementById("result-analysis");
const resultIcon = resultBox.querySelector(".result__icon");
const resultTitle = resultBox.querySelector(".result__title");

// Переводы кодов AI в человеческие подписи.
const SENTIMENT_RU = { positive: "позитивная", neutral: "нейтральная", negative: "негативная" };
const CATEGORY_RU = {
  order: "Заказ", question: "Вопрос", cooperation: "Сотрудничество",
  complaint: "Жалоба", spam: "Спам", other: "Прочее",
};
const PRIORITY_RU = { high: "высокий", medium: "средний", low: "низкий" };

function clearErrors() {
  document.querySelectorAll(".form__error").forEach((el) => (el.textContent = ""));
  form.querySelectorAll("input, textarea").forEach((el) => el.classList.remove("invalid"));
}

function showFieldErrors(details) {
  for (const [field, message] of Object.entries(details || {})) {
    const errorEl = document.querySelector(`[data-error-for="${field}"]`);
    const inputEl = document.getElementById(field);
    if (errorEl) errorEl.textContent = message;
    if (inputEl) inputEl.classList.add("invalid");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  resultBox.hidden = true;

  const payload = {
    name: form.name.value.trim(),
    phone: form.phone.value.trim(),
    email: form.email.value.trim(),
    message: form.message.value.trim(),
  };

  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/api/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (response.status === 201) {
      renderSuccess(data);
      form.reset();
    } else if (response.status === 422) {
      showFieldErrors(data.details);
    } else if (response.status === 429) {
      renderError(data.message || "Слишком много запросов. Попробуйте позже.");
    } else {
      renderError(data.message || "Что-то пошло не так. Попробуйте позже.");
    }
  } catch (error) {
    // Сюда попадаем, если сервер недоступен / нет сети.
    renderError("Не удалось связаться с сервером. Проверьте подключение.");
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtn.textContent = isLoading ? "Отправляю…" : "Отправить обращение";
}

function renderSuccess(data) {
  const analysis = data.analysis || {};
  resultBox.classList.remove("result--error");
  resultIcon.textContent = "✓";
  resultTitle.textContent = "Обращение принято";
  resultText.textContent = data.message || "Спасибо! Мы получили ваше обращение.";

  const sentimentClass =
    analysis.sentiment === "positive" ? "tag--pos"
    : analysis.sentiment === "negative" ? "tag--neg"
    : "";

  resultAnalysis.innerHTML = `
    <span class="tag ${sentimentClass}">Тональность: <b>${SENTIMENT_RU[analysis.sentiment] || "—"}</b></span>
    <span class="tag">Категория: <b>${CATEGORY_RU[analysis.category] || "—"}</b></span>
    <span class="tag">Приоритет: <b>${PRIORITY_RU[analysis.priority] || "—"}</b></span>
    <span class="tag">AI: <b>${analysis.provider === "claude" ? "Claude" : "fallback"}</b></span>
  `;

  resultBox.hidden = false;
  resultBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderError(message) {
  resultBox.classList.add("result--error");
  resultIcon.textContent = "!";
  resultTitle.textContent = "Не получилось";
  resultText.textContent = message;
  resultAnalysis.innerHTML = "";
  resultBox.hidden = false;
}
