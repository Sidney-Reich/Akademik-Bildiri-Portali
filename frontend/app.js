// shared by the T1 screens
const token = () => sessionStorage.getItem("token");
const FIELDS = { full_name: "ad soyad", email: "e-posta", password: "parola", orcid: "ORCID",
                 share: "katkı payı", title: "başlık", abstract: "özet", file: "dosya" };

function show(text, isError) {
  const box = document.getElementById("message");
  box.textContent = text;
  box.className = isError ? "error" : "";
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token()) headers.Authorization = "Bearer " + token();
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && token()) {
    sessionStorage.removeItem("token");
    location.href = "login.html";
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail;
    throw new Error(Array.isArray(detail)
      ? "Geçersiz veya eksik alan: " + detail.map(d => FIELDS[d.loc.at(-1)] || d.loc.at(-1)).join(", ")
      : detail || "İstek başarısız oldu (" + response.status + ").");
  }
  return data;
}

function requireLogin() {
  if (!token()) location.href = "login.html";
}

// element("td", "text", child, ...) -- text is never treated as HTML
function element(tag, ...children) {
  const e = document.createElement(tag);
  e.append(...children.map(c => c ?? ""));
  return e;
}

// the same header on every screen
(function header() {
  const here = location.pathname.split("/").pop() || "index.html";
  const link = (href, text) => {
    const a = element("a", text);
    a.href = href;
    if (href === here) a.setAttribute("aria-current", "page");
    return a;
  };
  const links = token()
    ? [link("mine.html", "Bildirilerim"), link("submit.html", "Bildiri gönder"), link("account.html", "Hesabım")]
    : [link("login.html", "Giriş yap"), link("register.html", "Kayıt ol")];
  if (token()) {
    const out = link("login.html", "Çıkış");
    out.onclick = () => sessionStorage.removeItem("token");
    links.push(out);
  }
  const brand = element("a", "Akademik Bildiri Portalı");
  brand.href = "index.html";
  brand.className = "brand";
  const bar = element("div", brand, element("nav", ...links));
  bar.className = "bar";
  const top = element("header", bar);
  top.className = "top";
  document.body.prepend(top);
})();

// the browser's own file button is in the browser's language, so we draw our own;
// the real input lies invisibly on top (keyboard, drag and drop, "required" still work)
function filePicker(input) {
  const name = element("span", "Dosya seçilmedi");
  const choose = element("span", "Dosya seç");
  choose.className = "choose";
  const box = element("span", choose, name);
  box.className = "file";
  input.replaceWith(box);
  box.append(input);
  input.addEventListener("change", () =>
    name.textContent = input.files[0]?.name || "Dosya seçilmedi");
  return box;
}
