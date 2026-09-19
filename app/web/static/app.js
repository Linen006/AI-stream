const $ = (selector) => document.querySelector(selector);

const state = {
  active: "overview",
  renderers: {},
  tasks: {},
  titles: { overview: "概览", products: "商品库", agent: "脚本助手", workflow: "AI工作流", analysis: "数据复盘", knowledge: "知识库" },
};

async function apiGet(url) {
  const response = await fetch(url);
  return response.json();
}

async function apiPost(url, body) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  return response.json();
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function closeNavigation() {
  document.body.classList.remove("nav-open");
}

function switchView(name) {
  state.active = name;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  $("#pageTitle").textContent = state.titles[name] || "工作台";
  closeNavigation();
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (name === "overview") loadOverview();
  if (name === "products") loadProducts();
  if (name === "workflow") loadWorkflowProducts();
  if (name === "knowledge") loadKnowledge();
}

async function loadHealth() {
  try {
    const data = await apiGet("/api/health");
    const chip = $("#apiChip");
    chip.innerHTML = data.api_ready ? '<i class="bi bi-check-circle-fill"></i> API 已配置' : '<i class="bi bi-exclamation-circle"></i> 未配置 API Key';
    chip.className = `status-chip${data.api_ready ? " success" : ""}`;
    $("#mockChip").style.display = data.mock_ai ? "inline-flex" : "none";
  } catch (error) {
    $("#apiChip").innerHTML = '<i class="bi bi-wifi-off"></i> 服务未连接';
    $("#apiChip").className = "status-chip";
  }
}

async function loadOverview() {
  try {
    const data = await apiGet("/api/overview");
    $("#statProducts").textContent = data.products;
    $("#statScripts").textContent = data.scripts;
    $("#statVideos").textContent = data.videos;
    $("#statCost").textContent = `¥${data.total_cost.toLocaleString()}`;
    $("#statRevenue").textContent = `¥${data.total_revenue.toLocaleString()}`;
    $("#statRoi").textContent = data.overall_roi;
  } catch (error) {
    $("#statProducts").textContent = "加载失败";
  }
  loadRecent();
  loadKnowledgePreview();
}

const recentIcons = { script: "bi-file-earmark-text", video: "bi-play-btn", review: "bi-bar-chart" };
const recentLabels = { script: "脚本", video: "视频", review: "复盘" };

async function loadRecent() {
  const holder = $("#recentList");
  try {
    const data = await apiGet("/api/recent");
    if (!data.items.length) {
      holder.innerHTML = '<div class="empty-state">暂无近期产出，运行一次脚本或工作流后会显示在这里。</div>';
      return;
    }
    const rows = data.items.slice(0, 5).map((item) => `
      <div class="recent-row">
        <span class="recent-kind"><i class="bi ${recentIcons[item.type] || "bi-file-earmark"}"></i></span>
        <span class="recent-copy"><strong>${escapeHtml(item.title || item.id)}</strong><small>${recentLabels[item.type] || "产出"} · ${escapeHtml(item.id)}</small></span>
        <span class="tag">${escapeHtml(item.status || "已保存")}</span>
      </div>`).join("");
    holder.innerHTML = `<div class="recent-head"><span>类型</span><span>内容</span><span>状态</span></div>${rows}`;
  } catch (error) {
    holder.innerHTML = '<div class="empty-state">近期产出加载失败</div>';
  }
}

async function loadKnowledgePreview() {
  const holder = $("#knowledgePreview");
  try {
    const data = await apiGet("/api/knowledge");
    holder.innerHTML = data.items.length
      ? data.items.slice(0, 6).map((item) => `<button class="knowledge-link" data-go="knowledge"><i class="bi bi-file-earmark-text"></i><span>${escapeHtml(item.key)}</span></button>`).join("")
      : '<div class="empty-state">暂无知识库资源</div>';
  } catch (error) {
    holder.innerHTML = '<div class="empty-state">知识库加载失败</div>';
  }
}

function productRow(product) {
  return `<tr>
    <td>${escapeHtml(product.id)}</td>
    <td><span class="table-product"><strong>${escapeHtml(product.name)}</strong><small>${escapeHtml(product.category || "未分类")}</small></span></td>
    <td>${escapeHtml(product.category || "-")}</td><td>${escapeHtml(product.price || "-")}</td><td>${escapeHtml(product.heat_score || "-")}</td>
    <td>${escapeHtml(product.target_audience || "-")}</td><td>${escapeHtml(product.selling_points || "-")}</td>
    <td><span class="tag">${escapeHtml(product.status || "-")}</span></td>
    <td><span class="table-actions"><button class="btn ghost" data-name="${escapeHtml(product.name)}" data-action="agent">生成脚本</button><button class="btn ghost" data-id="${escapeHtml(product.id)}" data-action="workflow">跑工作流</button></span></td>
  </tr>`;
}

async function loadProducts() {
  try {
    const data = await apiGet("/api/products");
    $("#productsBody").innerHTML = data.products.length ? data.products.map(productRow).join("") : '<tr><td colspan="9"><div class="empty-state">暂无商品</div></td></tr>';
  } catch (error) {
    $("#productsBody").innerHTML = '<tr><td colspan="9"><div class="empty-state">商品加载失败</div></td></tr>';
  }
}

async function loadWorkflowProducts(selectedId) {
  try {
    const data = await apiGet("/api/products");
    $("#workflowProduct").innerHTML = data.products.map((product) => `<option value="${escapeHtml(product.id)}">${escapeHtml(product.name)}（${escapeHtml(product.price)}）</option>`).join("");
    if (selectedId) $("#workflowProduct").value = selectedId;
  } catch (error) {
    $("#workflowProduct").innerHTML = "<option>加载失败</option>";
  }
}

async function loadKnowledge() {
  try {
    const data = await apiGet("/api/knowledge");
    $("#knowledgeGrid").innerHTML = data.items.length
      ? data.items.map((item) => `<details class="kb-card"><summary><span>${escapeHtml(item.key)}</span><span class="tag">${escapeHtml(item.version || "v1.0")}</span></summary><div class="meta">${escapeHtml(item.category || "未分类")} · ${escapeHtml(item.description || "暂无说明")}</div><div class="prompt">${escapeHtml(item.prompt || "")}</div></details>`).join("")
      : '<div class="empty-state">暂无提示词</div>';
  } catch (error) {
    $("#knowledgeGrid").innerHTML = '<div class="empty-state">知识库加载失败</div>';
  }
}

function startTask(taskId, renderer) {
  state.renderers[taskId] = renderer;
  state.tasks[taskId] = true;
  showTaskBar("running");
  pollTask(taskId);
}

function showTaskBar(status, taskId) {
  const bar = $("#taskBar");
  const dot = $("#taskDot");
  const message = $("#taskMsg");
  const logs = $("#taskLogs");
  if (status === "running") {
    bar.classList.add("show");
    dot.className = "task-state";
    dot.innerHTML = '<i class="bi bi-arrow-repeat spin"></i>';
    message.textContent = "任务运行中，请稍候...";
    logs.textContent = "";
  } else if (status === "done") {
    dot.className = "task-state done";
    dot.innerHTML = '<i class="bi bi-check-lg"></i>';
    message.textContent = "任务已完成";
    const task = state.tasks[taskId];
    if (task) logs.textContent = task.logs || "结果已写入本地数据。";
    loadOverview();
    setTimeout(() => bar.classList.remove("show"), 5000);
  } else if (status === "failed") {
    dot.className = "task-state failed";
    dot.innerHTML = '<i class="bi bi-x-lg"></i>';
    message.textContent = "任务失败";
    const task = state.tasks[taskId];
    if (task) logs.textContent = task.error || task.logs || "";
    setTimeout(() => bar.classList.remove("show"), 8000);
  }
}

async function pollTask(taskId) {
  const data = await apiGet(`/api/tasks?id=${encodeURIComponent(taskId)}`);
  const task = data.task;
  if (!task) return;
  state.tasks[taskId] = task;
  if (task.status === "running") {
    setTimeout(() => pollTask(taskId), 1500);
    return;
  }
  const renderer = state.renderers[taskId];
  if (renderer) renderer(task);
  showTaskBar(task.status, taskId);
}

function taskError(holder, task) {
  holder.innerHTML = `<div class="error-box">任务失败：${escapeHtml(task.error || "未知错误")}</div>`;
}

function renderAgentResult(task) {
  const box = $("#agentResult");
  if (task.status === "failed") return taskError(box, task);
  const result = task.result || {};
  box.innerHTML = `<div class="result-box"><div class="meta">脚本编号：${escapeHtml(result.script_id || "-")} · 已保存：${escapeHtml(result.saved_to || "-")}</div><strong>AI 商品分析</strong><pre></pre><strong>智能体输出</strong><pre></pre></div>`;
  const blocks = box.querySelectorAll("pre");
  blocks[0].textContent = result.suggestion || "";
  blocks[1].textContent = result.result || "";
}

function renderWorkflowResult(task) {
  const box = $("#workflowResult");
  if (task.status === "failed") return taskError(box, task);
  const result = task.result || {};
  box.innerHTML = `<div class="result-box"><div class="meta">商品：${escapeHtml(result.product_name || "-")} · 脚本 ${escapeHtml(result.script_id || "-")} · 内容 ${escapeHtml(result.content_id || "-")} · 输出目录：${escapeHtml(result.output_dir || "-")}</div><strong>工作流步骤输出</strong><div id="workflowSteps"></div></div>`;
  const holder = box.querySelector("#workflowSteps");
  (result.steps || []).forEach((step) => {
    const section = document.createElement("section");
    const title = document.createElement("strong");
    const content = document.createElement("pre");
    title.textContent = `步骤${step.step} ${step.title}`;
    content.textContent = step.content;
    section.append(title, content);
    holder.append(section);
  });
}

function renderAnalysisResult(task) {
  const box = $("#analysisResult");
  if (task.status === "failed") return taskError(box, task);
  const result = task.result || {};
  const rows = (result.rows || []).map((metric) => `<tr><td>${escapeHtml(metric.video_id)}</td><td>${escapeHtml(metric.video_name)}</td><td>${metric.views}</td><td>${metric.ctr}</td><td>${metric.conv}</td><td>${metric.revenue}</td><td>${metric.cost}</td><td>${metric.roi}</td><td>${metric.drop2s}</td></tr>`).join("");
  box.innerHTML = `<div class="result-box"><div class="meta">复盘编号：${escapeHtml(result.review_id || "-")} · 整体 ROI：${escapeHtml(result.overall_roi)} · 已保存：${escapeHtml(result.saved_to || "-")}</div><div class="table-wrap"><table><thead><tr><th>编号</th><th>视频</th><th>播放量</th><th>CTR%</th><th>转化率%</th><th>成交额</th><th>成本</th><th>ROI</th><th>跳出率%</th></tr></thead><tbody>${rows}</tbody></table></div><strong>AI 复盘报告</strong><pre></pre></div>`;
  box.querySelector("pre").textContent = result.ai_report || "";
}

document.addEventListener("click", (event) => {
  const nav = event.target.closest(".nav-item");
  if (nav) {
    location.hash = nav.dataset.view;
    switchView(nav.dataset.view);
    return;
  }
  const go = event.target.closest("[data-go]");
  if (go) {
    location.hash = go.dataset.go;
    switchView(go.dataset.go);
  }
});

$("#menuButton").addEventListener("click", () => document.body.classList.toggle("nav-open"));
$("#sidebarScrim").addEventListener("click", closeNavigation);

$("#productsBody").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.action === "agent") {
    $("#agentName").value = button.dataset.name;
    location.hash = "agent";
    switchView("agent");
  } else if (button.dataset.action === "workflow") {
    location.hash = "workflow";
    switchView("workflow");
    loadWorkflowProducts(button.dataset.id);
  }
});

$("#agentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#agentRunBtn");
  button.disabled = true;
  const data = await apiPost("/api/agent/generate", { product_name: $("#agentName").value.trim(), audience: $("#agentAudience").value.trim() || null, scenario: $("#agentScenario").value.trim() || null, sell: $("#agentSell").value.trim() || null, mock: $("#agentMock").checked });
  if (data.error) $("#agentResult").innerHTML = `<div class="error-box">${escapeHtml(data.error)}</div>`;
  else { $("#agentResult").innerHTML = '<div class="empty-state">AI 生成中，请稍候...</div>'; startTask(data.task_id, renderAgentResult); }
  button.disabled = false;
});

$("#workflowForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#workflowRunBtn");
  button.disabled = true;
  const data = await apiPost("/api/workflow/run", { product_id: $("#workflowProduct").value, mock: $("#workflowMock").checked });
  if (data.error) $("#workflowResult").innerHTML = `<div class="error-box">${escapeHtml(data.error)}</div>`;
  else { $("#workflowResult").innerHTML = '<div class="empty-state">工作流运行中，每步会写入数据表...</div>'; startTask(data.task_id, renderWorkflowResult); }
  button.disabled = false;
});

$("#analysisRunBtn").addEventListener("click", async () => {
  const button = $("#analysisRunBtn");
  button.disabled = true;
  const data = await apiPost("/api/analysis/run", { mock: $("#analysisMock").checked });
  if (data.error) $("#analysisResult").innerHTML = `<div class="error-box">${escapeHtml(data.error)}</div>`;
  else { $("#analysisResult").innerHTML = '<div class="empty-state">AI 复盘生成中，请稍候...</div>'; startTask(data.task_id, renderAnalysisResult); }
  button.disabled = false;
});

(function init() {
  const hash = (location.hash || "").replace("#", "");
  if (Object.hasOwn(state.titles, hash)) switchView(hash);
  loadHealth();
  loadOverview();
})();
