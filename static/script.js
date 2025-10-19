const $ = (id) => document.getElementById(id);
const qs = (sel, root = document) => root.querySelector(sel);
const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function fmtBytes(n) {
  if (!Number.isFinite(n)) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function fmtDuration(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "0:00 min";
  const m = Math.floor(sec / 60),
    s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")} min`;
}

function setTextSafe(el, txt) {
  if (el) el.textContent = txt;
}

function setStep(active) {
  const steps = [$("step1"), $("step2"), $("step3"), $("step4")].filter(
    Boolean
  );
  steps.forEach((n, i) => n.classList.toggle("active", i <= active));
}

const BYTES_MB = 1024 * 1024;
const T1_MAX = 500 * BYTES_MB;
const T2_MAX = 1024 * BYTES_MB;
const PRICE_MATRIX = {
  gmail: [1.99, 2.99, 4.49],
  outlook: [2.19, 3.29, 4.99],
  other: [2.49, 3.99, 5.49],
};
const UPSALE = { priority: 0.75, transcript: 1.5 };

const state = {
  file: null,
  uploadId: null,
  durationSec: 0,
  sizeBytes: 0,
  provider: "gmail",
  tier: 1,
  pricing: {
    base: 0,
    priority: 0,
    transcript: 0,
    subtotal: 0,
    tax: 0,
    total: 0,
    priceCents: 0,
  },
};

function calcTotals() {
  const baseEl = $("basePrice");
  const priEl = $("priorityPrice");
  const traEl = $("transcriptPrice");
  const taxEl = $("taxAmount");
  const totEl = $("totalAmount");

  const provider = state.provider || "gmail";
  const tier = state.uploadId
    ? state.sizeBytes <= T1_MAX
      ? 1
      : state.sizeBytes <= T2_MAX
      ? 2
      : 3
    : 1;
  state.tier = tier;

  const base = PRICE_MATRIX[provider][tier - 1];
  const pri = $("priority")?.checked ? UPSALE.priority : 0;
  const tra = $("transcript")?.checked ? UPSALE.transcript : 0;

  const subtotal = base + pri + tra;
  const tax = +(subtotal * 0.1).toFixed(2);
  const total = +(subtotal + tax).toFixed(2);

  state.pricing = {
    base,
    priority: pri,
    transcript: tra,
    subtotal,
    tax,
    total,
    priceCents: Math.round(total * 100),
  };

  setTextSafe(baseEl, `$${base.toFixed(2)}`);
  setTextSafe(priEl, `$${pri.toFixed(2)}`);
  setTextSafe(traEl, `$${tra.toFixed(2)}`);
  setTextSafe(taxEl, `$${tax.toFixed(2)}`);
  setTextSafe(totEl, `$${total.toFixed(2)}`);

  const btn = $("processButton");
  if (btn)
    btn.innerHTML = `<i class="fas fa-credit-card"></i> Pay &amp; Compress ($${total.toFixed(
      2
    )})`;

  // Highlight totals by provider in the small "Totals" table
  ["gmail", "outlook", "other"].forEach((prov) => {
    const el = $(`ptTotal${prov.charAt(0).toUpperCase() + prov.slice(1)}`);
    if (el) el.style.fontWeight = prov === provider ? "700" : "400";
  });
}

function wireUpload() {
  const uploadArea = $("uploadArea");
  const fileInput = $("fileInput");
  const fileInfo = $("fileInfo");
  if (!uploadArea || !fileInput) return;

  const openPicker = () => fileInput.click();
  ["click", "keypress"].forEach((evt) => {
    uploadArea.addEventListener(evt, (e) => {
      if (e.type === "keypress" && e.key !== "Enter" && e.key !== " ") return;
      openPicker();
    });
  });

  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
  });
  uploadArea.addEventListener("dragleave", () =>
    uploadArea.classList.remove("dragover")
  );
  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
    if (e.dataTransfer?.files?.[0]) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files?.[0]) handleFile(fileInput.files[0]);
  });

  $("removeFile")?.addEventListener("click", () => {
    state.file = null;
    state.uploadId = null;
    fileInput.value = "";
    if (fileInfo) fileInfo.style.display = "none";
    const up = $("uploadProgress");
    if (up) up.style.display = "none";
    setStep(0);
    calcTotals();
  });
}

function wireProviderSelection() {
  const providerButtons = qsa(".provider-card");
  if (!providerButtons.length) return;

  providerButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      providerButtons.forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");

      const provider = btn.dataset.provider || "gmail";
      state.provider = provider;

      // Highlight active provider column in pricing table
      qsa("[data-col]").forEach((el) => {
        el.style.background =
          el.getAttribute("data-col") === provider ? "#eef6ff" : "";
        el.style.fontWeight =
          el.getAttribute("data-col") === provider ? "600" : "400";
      });

      calcTotals();
    });
  });
}

function setUploadProgress(pct, note = "Uploading…") {
  const box = $("uploadProgress");
  const fill = $("uploadFill");
  const pctEl = $("uploadPct");
  const noteEl = $("uploadNote");
  if (box) box.style.display = "";
  const clamped = Math.max(0, Math.min(100, Math.floor(pct)));
  if (fill) fill.style.width = `${clamped}%`;
  if (pctEl) pctEl.textContent = `${clamped}%`;
  if (noteEl) {
    noteEl.style.display = "";
    noteEl.textContent = note;
  }
}

async function handleFile(file) {
  state.file = file;

  setTextSafe($("fileName"), file.name);
  setTextSafe($("fileSize"), fmtBytes(file.size));
  setTextSafe($("fileDuration"), "probing…");
  if ($("fileInfo")) $("fileInfo").style.display = "";

  const dur = await new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => resolve(v.duration || 0);
    v.onerror = () => resolve(0);
    v.src = URL.createObjectURL(file);
  });

  const email = $("userEmail")?.value?.trim() || "noemail@mailsized.com";
  const payload = {
    filename: file.name,
    size_bytes: file.size,
    duration_sec: dur,
    content_type: file.type || "video/mp4",
    email,
  };

  const res = await fetch("/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!data.ok) return showError(data.detail || "Upload request failed");

  state.uploadId = data.upload_id;
  state.sizeBytes = file.size;
  state.durationSec = dur;

  const s3UploadRes = await fetch(data.presigned_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!s3UploadRes.ok) return showError("Upload to S3 failed.");

  setUploadProgress(100, "Upload complete");
  setTextSafe($("fileDuration"), fmtDuration(dur));
  setStep(1);
  calcTotals();
}

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v || "");
}

async function syncEmail(uploadId, email) {
  try {
    await fetch("/update_email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ upload_id: uploadId, email }),
    });
  } catch (err) {
    console.warn("⚠️ Email sync failed:", err);
  }
}

function wireCheckout() {
  const btn = $("processButton");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    hideError();
    if (!state.file || !state.uploadId)
      return showError("Please upload a video first.");

    const email = $("userEmail")?.value?.trim();
    if (!validEmail(email)) return showError("Enter a valid email.");
    if (!$("agree")?.checked)
      return showError("Please accept the Terms & Conditions.");

    await syncEmail(state.uploadId, email);

    const coupon = $("couponInput")?.value?.trim() || "";
    calcTotals();

    const devPayload = {
      upload_id: state.uploadId,
      token: "DEVTEST",
      provider: state.provider || "other",
      priority: !!$("priority")?.checked,
      transcript: !!$("transcript")?.checked,
    };

    if (coupon.toUpperCase() === "DEVTEST") {
      try {
        const res = await fetch("/devtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(devPayload),
        });
        const data = await res.json();
        if (data.ok) {
          setStep(2);
          $("postPaySection").style.display = "";
          startSSE(state.uploadId);
        } else {
          showError(data?.error || data?.detail || "DEVTEST failed.");
        }
      } catch {
        showError("DEVTEST failed. Try again.");
      }
      return;
    }

    if (state.sizeBytes <= 50 * 1024 * 1024) {
      try {
        const res = await fetch("/devtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(devPayload),
        });
        const data = await res.json();
        if (data.ok) {
          setStep(2);
          $("postPaySection").style.display = "";
          startSSE(state.uploadId);
        } else {
          showError(
            data?.error || data?.detail || "Free-tier compression failed."
          );
        }
      } catch {
        showError("Free-tier job failed. Try again.");
      }
      return;
    }

    const payload = {
      file_key: state.uploadId,
      provider: state.provider,
      priority: !!$("priority")?.checked,
      transcript: !!$("transcript")?.checked,
      email,
      promo_code: coupon,
      size_bytes: state.sizeBytes,
      duration_sec: state.durationSec,
      price_cents: state.pricing?.priceCents ?? 0,
      filename: state.file?.name || "",
    };

    let res;
    try {
      res = await fetch("/api/pay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch {
      return showError("Could not start checkout.");
    }

    let data = {};
    try {
      data = await res.json();
    } catch {
      return showError("Unexpected server response.");
    }

    const url = data?.url || data?.checkout_url;
    if (!url) return showError("Checkout could not be created.");

    setStep(1);
    window.location.href = url;
  });
}

function revealDownload(url) {
  const dlLink = $("downloadLink");
  const downloadSection = $("downloadSection");
  const emailNote = $("emailNote");
  const progressNote = $("progressNote");

  if (!url) return showError("Download link unavailable. Please refresh.");

  if (dlLink) {
    dlLink.href = url;
    dlLink.target = "_blank";
    dlLink.download = "";
  }

  if (downloadSection) downloadSection.style.display = "block";
  if (emailNote) emailNote.style.display = "";
  if (progressNote)
    progressNote.textContent = "✅ Compression Complete! Ready to download.";
  setStep(3);

  try {
    downloadSection?.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch {}
  console.log("✅ Download ready:", url);
}

function startSSE(jobId) {
  const pctEl = $("progressPct");
  const fillEl = $("progressFill");
  const noteEl = $("progressNote");

  try {
    const es = new EventSource(`/events/${encodeURIComponent(jobId)}`);
    es.onmessage = async (evt) => {
      let data = {};
      try {
        data = JSON.parse(evt.data || "{}");
      } catch {}

      const p = Number(data.progress || 0);
      if (pctEl) pctEl.textContent = `${Math.floor(p)}%`;
      if (fillEl) fillEl.style.width = `${Math.floor(p)}%`;
      if (noteEl) noteEl.textContent = data.message || "Working…";

      if (data.download_url) {
        revealDownload(data.download_url);
        es.close();
      }

      if (data.status === "done") {
        try {
          const r = await fetch(`/download/${encodeURIComponent(jobId)}`);
          const j = await r.json();
          if (j?.url) revealDownload(j.url);
          else showError("No download URL. Try refreshing.");
        } catch {
          showError("Couldn’t fetch download URL.");
        } finally {
          es.close();
        }
      } else if (data.status === "error") {
        es.close();
        showError(data.message || "Compression failed.");
        if (noteEl) noteEl.textContent = "Error";
      }
    };
  } catch {}
}

function showError(msg) {
  const box = $("errorContainer");
  const msgEl = $("errorMessage");
  if (msgEl) msgEl.textContent = String(msg || "Something went wrong.");
  if (box) box.style.display = "";
}

function hideError() {
  const box = $("errorContainer");
  if (box) box.style.display = "none";
}

document.addEventListener("DOMContentLoaded", () => {
  wireUpload();
  wireCheckout();
  wireProviderSelection(); // ✅ Added
  calcTotals();
});
