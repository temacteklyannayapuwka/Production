const menuLayer = document.querySelector('.menu-layer');
const menuDrawer = menuLayer?.querySelector('.menu-drawer');
const toast = document.querySelector('.toast');
let toastTimer;
let menuReturnFocus;

const menuFocusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function setMenu(open) {
  if (!menuLayer) return;
  const wasOpen = menuLayer.classList.contains('is-open');
  if (wasOpen === open) return;
  if (open) menuReturnFocus = document.activeElement;
  menuLayer?.classList.toggle('is-open', open);
  menuLayer?.setAttribute('aria-hidden', String(!open));
  document.body.classList.toggle('menu-open', open);
  document.querySelectorAll('[data-menu-trigger]').forEach((trigger) => trigger.setAttribute('aria-expanded', String(open)));
  if (open) {
    document.querySelector('#drawer-search')?.focus();
  } else if (menuReturnFocus instanceof HTMLElement) {
    menuReturnFocus.focus();
    menuReturnFocus = null;
  }
}

function keepFocusInsideMenu(event) {
  if (event.key !== 'Tab' || !menuLayer?.classList.contains('is-open') || !menuDrawer) return;
  const focusable = [...menuDrawer.querySelectorAll(menuFocusableSelector)]
    .filter((element) => element instanceof HTMLElement && element.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
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
menuLayer?.addEventListener('keydown', keepFocusInsideMenu);
document.addEventListener('click', (event) => { if (event.target.closest('[data-subscribe]')) showToast('Спасибо! Форма подписки появится на следующем этапе.'); });

if (document.querySelector('.city-hero') && document.querySelector('#news-feed')) {
  document.documentElement.classList.add('hero-snap-enabled');
}
