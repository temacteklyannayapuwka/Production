const menuLayer = document.querySelector('.menu-layer');
const toast = document.querySelector('.toast');
let toastTimer;

function setMenu(open) {
  menuLayer?.classList.toggle('is-open', open);
  menuLayer?.setAttribute('aria-hidden', String(!open));
  document.body.classList.toggle('menu-open', open);
  document.querySelectorAll('[data-menu-trigger]').forEach((trigger) => trigger.setAttribute('aria-expanded', String(open)));
  if (open) document.querySelector('#drawer-search')?.focus();
}

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}

document.querySelectorAll('[data-menu-trigger]').forEach((button) => button.addEventListener('click', () => setMenu(true)));
document.querySelectorAll('[data-menu-close], .drawer-nav a, .drawer-editorial').forEach((item) => item.addEventListener('click', () => setMenu(false)));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setMenu(false); });
document.addEventListener('click', (event) => { if (event.target.closest('[data-subscribe]')) showToast('Спасибо! Форма подписки появится на следующем этапе.'); });
