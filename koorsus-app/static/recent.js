renderRecent = function () {
  var list = loadRecent();
  document.getElementById("recent-count").textContent = list.length;
  var box = document.getElementById("recent-list");
  if (!list.length) {
    box.innerHTML = '<div class="empty">No history yet.</div>';
    return;
  }
  box.innerHTML = "";
  list.forEach(function (item, idx) {
    var d = document.createElement("div");
    d.className = "item";
    var head = document.createElement("div");
    head.className = "qsmall";
    head.textContent = "Q: " + item.q + " ";
    var btn = document.createElement("button");
    btn.className = "ghost";
    btn.textContent = "View";
    btn.addEventListener("click", function () { showRecent(idx); });
    head.appendChild(btn);
    var small = document.createElement("div");
    small.className = "asmall";
    small.textContent = (item.a || "").slice(0, 140) + "...";
    d.appendChild(head);
    d.appendChild(small);
    box.appendChild(d);
  });
};

showRecent = function (idx) {
  var list = loadRecent();
  var item = list[idx];
  if (!item) { alert("That entry is no longer in history."); return; }
  var box = document.getElementById("answer");
  var q = document.createElement("div");
  q.className = "q";
  q.textContent = "Q: " + item.q;
  var a = document.createElement("div");
  a.className = "a";
  a.textContent = item.a || "";
  box.innerHTML = "";
  box.appendChild(q);
  box.appendChild(a);
  if (item.sources && item.sources.length) {
    var s = document.createElement("div");
    s.className = "src";
    s.textContent = "Sources: " + item.sources.join(", ");
    box.appendChild(s);
  }
  box.scrollIntoView({behavior: "smooth", block: "center"});
};
