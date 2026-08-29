const toast = document.querySelector(".toast");
let toastTimer;

const sectionLinks = [
  ["society", "Общество"], ["politics", "Политика"], ["economy", "Экономика"],
  ["incidents", "Происшествия"], ["sport", "Спорт"], ["culture", "Культура"], ["afisha", "Афиша"],
];

function navigation(active = "") {
  return sectionLinks.map(([slug, label]) => `<a class="${active === slug ? "active" : ""}" href="${slug}.html">${label}</a>`).join("");
}

function brand(extraClass = "") {
  return `<a class="brand ${extraClass}" href="index.html" aria-label="Ставрополь+, на главную"><b>С+</b><span><strong>Ставрополь+</strong><small>Город. Люди. События.</small></span></a>`;
}

function placeSharedLayout() {
  const active = document.body.dataset.section || "";
  const header = document.querySelector("[data-site-header]");
  const footer = document.querySelector("[data-site-footer]");

  if (header) {
    header.innerHTML = `<header class="masthead"><div class="shell masthead__inner">${brand()}<div class="masthead__tools"><div class="social" aria-label="Социальные сети"><a href="#" aria-label="ВКонтакте">VK</a><a href="#" aria-label="Telegram">TG</a><a href="#" aria-label="Одноклассники">OK</a><a class="social__max" href="#">MAX</a></div><form class="search" id="search-form"><label class="sr-only" for="search">Поиск новостей</label><input id="search" name="search" placeholder="Поиск новостей" /><button type="submit" aria-label="Найти">⌕</button></form></div><button class="menu-button" type="button" data-menu-trigger aria-label="Открыть меню" aria-controls="site-menu" aria-expanded="false"><i></i><span>Меню</span></button></div></header>
      <nav class="nav"><div class="shell nav__inner"><a class="${active ? "" : "active"}" href="index.html">Главная</a>${navigation(active)}</div></nav>`;
  }

  if (footer) {
    footer.innerHTML = `<footer><div class="shell footer__grid"><section>${brand("brand--footer")}<p>Независимое медиа о жизни Ставропольского края и Северного Кавказа.</p></section><section><h2>Разделы</h2><a href="society.html">Общество</a><a href="politics.html">Политика</a><a href="economy.html">Экономика</a><a href="culture.html">Культура</a></section><section><h2>Контакты</h2><p>news@stavplus.ru</p><p>Пятигорск, Кавказский проспект, 24</p></section></div><div class="shell copyright">© <span data-year></span> Ставрополь+. Экспериментальная концепция.</div></footer>`;
  }
}

function placeMenu() {
  if (document.querySelector(".menu-layer")) return;
  document.body.insertAdjacentHTML("beforeend", `<div class="menu-layer" aria-hidden="true"><div class="menu-backdrop" data-menu-close></div><aside class="menu-drawer" id="site-menu" aria-label="Главное меню" aria-modal="true" role="dialog"><div class="menu-drawer__top"><span>Навигация</span><button type="button" class="menu-close" data-menu-close aria-label="Закрыть меню">×</button></div><form class="drawer-search" id="drawer-search-form"><label class="sr-only" for="drawer-search">Поиск новостей</label><input id="drawer-search" placeholder="Поиск..." /><button type="submit" aria-label="Найти">⌕</button></form><nav class="drawer-nav" aria-label="Разделы"><a href="world.html">Мир</a><a href="society.html">Общество</a><a href="economy.html">Экономика</a><a href="politics.html">Политика</a><a href="science.html">Наука</a><a href="education.html">Образование</a><a href="culture.html">Культура</a><a href="incidents.html">Происшествия</a><a href="ecology.html">Экология</a><a href="health.html">Здоровье</a><a href="sport.html">Спорт</a></nav><a class="drawer-editorial" href="society.html">Редакция</a><div class="drawer-social" aria-label="Социальные сети"><a href="#">VK</a><a href="#">TG</a><a href="#">OK</a><a href="#">MAX</a></div></aside></div>`);
}

function setMenu(open) {
  const layer = document.querySelector(".menu-layer");
  if (!layer) return;
  layer.classList.toggle("is-open", open);
  layer.setAttribute("aria-hidden", String(!open));
  document.body.classList.toggle("menu-open", open);
  document.querySelectorAll("[data-menu-trigger]").forEach((trigger) => trigger.setAttribute("aria-expanded", String(open)));
  if (open) document.querySelector("#drawer-search")?.focus();
}

placeSharedLayout();
placeMenu();

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

document.querySelectorAll("[data-menu-trigger]").forEach((button) => button.addEventListener("click", () => setMenu(true)));
document.querySelectorAll("[data-menu-close], .drawer-nav a, .drawer-editorial").forEach((item) => item.addEventListener("click", () => setMenu(false)));
document.addEventListener("keydown", (event) => { if (event.key === "Escape") setMenu(false); });

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-subscribe]")) showToast("Спасибо! Форма подписки появится на следующем этапе.");
});

document.querySelectorAll("#search-form, #drawer-search-form").forEach((form) => form.addEventListener("submit", (event) => {
  event.preventDefault();
  const input = form.querySelector("input");
  const query = input?.value.trim();
  setMenu(false);
  showToast(query ? `Поиск по запросу «${query}» появится после подключения базы.` : "Введите запрос для поиска.");
}));

document.querySelectorAll("[data-year]").forEach((item) => { item.textContent = new Date().getFullYear(); });
