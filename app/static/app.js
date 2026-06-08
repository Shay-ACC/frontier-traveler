let gameId = null;
let isLoading = false;

const NPC_NAME_MAP = {
    innkeeper: "艾琳娜",
    mayor: "赫尔曼",
    miner: "托马斯"
};

document.addEventListener("DOMContentLoaded", function () {
    window.dialogLog = document.getElementById("dialog-log");
    window.errorDisplay = document.getElementById("error-display");
    window.inputText = document.getElementById("input-text");
    window.btnStart = document.getElementById("btn-start");
    window.btnSend = document.getElementById("btn-send");
    window.btnRefresh = document.getElementById("btn-refresh");
    window.inputRow = document.getElementById("input-row");
    window.gameIdEl = document.getElementById("game-id");
    window.currentLocationEl = document.getElementById("current-location");
    window.turnCountEl = document.getElementById("turn-count");
    window.relationshipsEl = document.getElementById("relationships");
    window.questStatesEl = document.getElementById("quest-states");
    window.memoriesEl = document.getElementById("memories");
    window.flagsEl = document.getElementById("flags");

    btnStart.onclick = startGame;
    btnSend.onclick = sendMessage;
    btnRefresh.onclick = function () {
        refreshState();
    };
    inputText.onkeydown = function (e) {
        if (e.key === "Enter") {
            sendMessage();
        }
    };
});

function addDialogBubble(type, content) {
    var div = document.createElement("div");
    switch (type) {
        case "player":
            div.className = "msg-player";
            break;
        case "npc":
            div.className = "msg-npc";
            break;
        case "system":
            div.className = "msg-system";
            break;
        case "error":
            div.className = "msg-error";
            break;
        default:
            div.className = "msg-system";
    }
    div.innerHTML = content;
    dialogLog.appendChild(div);
    div.scrollIntoView({ behavior: "smooth", block: "end" });
}

function showError(msg) {
    errorDisplay.textContent = msg;
    errorDisplay.style.display = "block";
    setTimeout(clearError, 3000);
}

function clearError() {
    errorDisplay.style.display = "none";
    errorDisplay.textContent = "";
}

function setLoading(loading) {
    isLoading = loading;
    btnSend.disabled = loading;
    btnRefresh.disabled = loading;
    inputText.disabled = loading;
}

function startGame() {
    btnStart.disabled = true;
    btnStart.textContent = "正在开始...";

    fetch("/game/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ player_name: "旅行者" })
    })
        .then(function (res) {
            if (!res.ok) throw new Error("服务器错误: " + res.status);
            return res.json();
        })
        .then(function (data) {
            if (data.error) throw new Error(data.error);

            gameId = data.game_id;
            gameIdEl.textContent = gameId || "-";

            if (data.opening_narrative) {
                addDialogBubble("system", data.opening_narrative);
            }

            btnStart.style.display = "none";
            inputRow.classList.remove("hidden");

            refreshState();
        })
        .catch(function (err) {
            showError("开始游戏失败: " + err.message);
            btnStart.disabled = false;
            btnStart.textContent = "开始游戏";
        });
}

function sendMessage() {
    var text = inputText.value.trim();
    if (!text || isLoading) return;

    clearError();
    addDialogBubble("player", escapeHtml(text));
    inputText.value = "";
    setLoading(true);

    fetch("/game/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameId, message: text })
    })
        .then(function (res) {
            if (!res.ok) throw new Error("服务器错误: " + res.status);
            return res.json();
        })
        .then(function (data) {
            if (data.error) throw new Error(data.error);

            var npcName = NPC_NAME_MAP[data.npc_id] || data.npc_id || "旁白";
            var npcTag = '<span class="npc-tag">' + escapeHtml(npcName) + "</span><br>";
            addDialogBubble("npc", npcTag + escapeHtml(data.npc_response || "(沉默)"));

            if (data.state_changes) {
                if (data.state_changes.quest_updates && data.state_changes.quest_updates.length > 0) {
                    data.state_changes.quest_updates.forEach(function (q) {
                        addDialogBubble("system", "📋 任务更新: " + escapeHtml(q.quest_id || q) + " → " + escapeHtml(q.current_stage || q.stage || ""));
                    });
                }
                if (data.state_changes.relationship_changes && data.state_changes.relationship_changes.length > 0) {
                    data.state_changes.relationship_changes.forEach(function (r) {
                        var rName = NPC_NAME_MAP[r.npc_id] || r.npc_id;
                        addDialogBubble("system", "💬 关系变化: " + escapeHtml(rName) + " 信任度 " + (r.change >= 0 ? "+" : "") + r.change);
                    });
                }
            }

            refreshState();
        })
        .catch(function (err) {
            showError("发送失败: " + err.message);
        })
        .finally(function () {
            setLoading(false);
        });
}

function refreshState() {
    if (!gameId) return;

    fetch("/game/state/" + gameId)
        .then(function (res) {
            if (!res.ok) throw new Error("服务器错误: " + res.status);
            return res.json();
        })
        .then(function (data) {
            if (data.error) throw new Error(data.error);

            gameIdEl.textContent = data.game_id || gameId;
            var ws = data.world_state || {};
            currentLocationEl.textContent = ws.current_location || "-";
            turnCountEl.textContent = ws.turn_count != null ? ws.turn_count : "-";

            if (data.relationships && data.relationships.length > 0) {
                relationshipsEl.innerHTML = "";
                data.relationships.forEach(function (r) {
                    var name = NPC_NAME_MAP[r.npc_id] || r.npc_id;
                    var trust = r.trust || 0;
                    var clampedTrust = Math.max(0, Math.min(100, trust));

                    var item = document.createElement("div");
                    item.className = "relationship-item";

                    var nameDiv = document.createElement("div");
                    nameDiv.className = "name";
                    nameDiv.textContent = name + " (信任: " + trust + ")";

                    var barContainer = document.createElement("div");
                    barContainer.className = "trust-bar-container";

                    var bar = document.createElement("div");
                    bar.className = "trust-bar";
                    bar.style.width = clampedTrust + "%";

                    barContainer.appendChild(bar);
                    item.appendChild(nameDiv);
                    item.appendChild(barContainer);
                    relationshipsEl.appendChild(item);
                });
            } else {
                relationshipsEl.innerHTML = '<p class="empty-hint">暂无数据</p>';
            }

            if (data.quest_states && data.quest_states.length > 0) {
                questStatesEl.innerHTML = "";
                data.quest_states.forEach(function (q) {
                    var item = document.createElement("div");
                    item.className = "quest-item";
                    item.innerHTML = '<span class="quest-id">' + escapeHtml(q.quest_id) + '</span><span class="quest-stage">' + escapeHtml(q.current_stage) + "</span>";
                    questStatesEl.appendChild(item);
                });
            } else {
                questStatesEl.innerHTML = '<p class="empty-hint">暂无数据</p>';
            }

            if (data.recent_memories && data.recent_memories.length > 0) {
                memoriesEl.innerHTML = "";
                data.recent_memories.forEach(function (m) {
                    if (typeof m === "string") {
                        var item = document.createElement("div");
                        item.className = "memory-item";
                        item.textContent = m;
                        memoriesEl.appendChild(item);
                        return;
                    }
                    var isLong = m.type === "long_term";
                    var isImportant = m.importance >= 7;
                    var npcName = NPC_NAME_MAP[m.npc_id] || m.npc_id || "";

                    var item = document.createElement("div");
                    item.className = "memory-item" + (isLong ? " memory-type-long" : " memory-type-short") + (isImportant ? " memory-important" : "");

                    var header = document.createElement("div");
                    header.className = "memory-header";
                    var typeLabel = isLong ? "长期" : "短期";
                    var star = isImportant ? "★" : "";
                    header.textContent = "[" + typeLabel + star + (m.importance != null ? m.importance : "") + "] 第" + (m.turn != null ? m.turn : "?") + "轮" + (npcName ? " - " + npcName : "");

                    var body = document.createElement("div");
                    body.className = "memory-body";
                    var content = m.content || "";
                    body.textContent = content.length > 80 ? content.substring(0, 80) + "..." : content;

                    item.appendChild(header);
                    item.appendChild(body);
                    memoriesEl.appendChild(item);
                });
            } else {
                memoriesEl.innerHTML = '<p class="empty-hint">暂无数据</p>';
            }

            if (data.world_state && data.world_state.flags) {
                var flags = data.world_state.flags;
                var keys = Object.keys(flags);
                if (keys.length > 0) {
                    flagsEl.innerHTML = "";
                    keys.forEach(function (k) {
                        var item = document.createElement("div");
                        item.className = "flag-item";
                        item.innerHTML = '<span class="flag-key">' + escapeHtml(k) + '</span>: <span class="flag-value">' + escapeHtml(String(flags[k])) + "</span>";
                        flagsEl.appendChild(item);
                    });
                } else {
                    flagsEl.innerHTML = '<p class="empty-hint">暂无数据</p>';
                }
            } else {
                flagsEl.innerHTML = '<p class="empty-hint">暂无数据</p>';
            }
        })
        .catch(function (err) {
            showError("刷新状态失败: " + err.message);
        });
}

function escapeHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
