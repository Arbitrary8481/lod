(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  // Relative URLs keep Home Assistant's ingress path prefix intact.
  const query = window.location.search;
  let hotkeys = {};
  let busy = false;

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  // "{G}green{0} plain" -> coloured spans
  function colourise(line) {
    let html = "";
    let open = false;
    for (const part of escapeHtml(line).split(/(\{[rRgGyYcCmMwW0]\})/)) {
      const m = /^\{(.)\}$/.exec(part);
      if (m) {
        if (open) html += "</span>";
        open = m[1] !== "0";
        if (open) html += `<span class="c-${m[1]}">`;
      } else {
        html += part;
      }
    }
    return open ? html + "</span>" : html;
  }

  function renderText(lines) {
    $("text").innerHTML = lines
      .map((l) => (l === "" ? '<p class="gap"></p>' : `<p>${colourise(l)}</p>`))
      .join("");
  }

  function renderNav(nav) {
    hotkeys = {};
    const box = $("nav");
    box.innerHTML = "";
    for (const section of nav) {
      if (!section.items.length) continue;
      if (section.h) {
        const h = document.createElement("h3");
        h.textContent = section.h;
        box.appendChild(h);
      }
      for (const item of section.items) {
        const b = document.createElement("button");
        b.type = "button";
        b.innerHTML = `<span class="k">${escapeHtml(item.k || "")}</span> ${colourise(item.label)}`;
        b.addEventListener("click", () => choose(item));
        box.appendChild(b);
        if (item.k) hotkeys[item.k.toUpperCase()] = item;
      }
    }
  }

  function renderStats(stats) {
    const box = $("stats");
    $("stats-wrap").hidden = !stats.length;
    box.innerHTML = "";
    for (const group of stats) {
      const h = document.createElement("h3");
      h.textContent = group.h;
      box.appendChild(h);
      for (const [label, value, frac] of group.rows) {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `<span>${escapeHtml(label)}</span><span>${escapeHtml(value)}</span>`;
        box.appendChild(row);
        if (typeof frac === "number") {
          const bar = document.createElement("div");
          bar.className = "bar";
          const pct = Math.max(0, Math.min(1, frac)) * 100;
          bar.innerHTML = `<i style="width:${pct}%"${pct < 30 ? ' class="low"' : ""}></i>`;
          box.appendChild(bar);
        }
      }
    }
  }

  function render(screen) {
    $("title").textContent = screen.title;
    document.title = `${screen.title} - Legend of Darkness`;
    renderText(screen.text);
    renderNav(screen.nav);
    renderStats(screen.stats);
    window.scrollTo({ top: 0 });
  }

  function setBusy(on) {
    busy = on;
    for (const b of $("nav").querySelectorAll("button")) b.disabled = on;
  }

  async function call(url, body) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(url + query, body ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      } : {});
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      render(await res.json());
    } catch (err) {
      $("text").insertAdjacentHTML("afterbegin",
        `<p class="error">Something went wrong: ${escapeHtml(String(err.message || err))}</p>`);
    } finally {
      setBusy(false);
    }
  }

  function ask(label) {
    return new Promise((resolve) => {
      const dlg = $("prompt");
      const input = $("prompt-input");
      $("prompt-label").textContent = label;
      input.value = "";
      const done = (value) => {
        dlg.close();
        $("prompt-form").onsubmit = null;
        $("prompt-cancel").onclick = null;
        resolve(value);
      };
      $("prompt-form").onsubmit = (e) => { e.preventDefault(); done(input.value); };
      $("prompt-cancel").onclick = () => done(null);
      dlg.oncancel = () => done(null);
      dlg.showModal();
      input.focus();
    });
  }

  async function choose(item) {
    if (busy) return;
    let value = null;
    if (item.prompt) {
      value = await ask(item.prompt);
      if (value === null || value.trim() === "") return;
    }
    call("api/action", { action: item.a, value });
  }

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || $("prompt").open) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "")) return;
    const item = hotkeys[e.key.toUpperCase()];
    if (item) {
      e.preventDefault();
      choose(item);
    }
  });

  call("api/state");
})();
