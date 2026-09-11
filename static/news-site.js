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

const backToTop = document.querySelector('[data-back-to-top]');
let scrollFramePending = false;

const updateBackToTop = () => {
  if (!backToTop) return;
  const visible = window.scrollY > Math.max(480, window.innerHeight * 0.75);
  backToTop.classList.toggle('is-visible', visible);
  backToTop.setAttribute('aria-hidden', String(!visible));
};

window.addEventListener('scroll', () => {
  if (scrollFramePending) return;
  scrollFramePending = true;
  window.requestAnimationFrame(() => {
    updateBackToTop();
    scrollFramePending = false;
  });
}, { passive: true });

backToTop?.addEventListener('click', () => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
});
updateBackToTop();

const cityHero = document.querySelector('.city-hero');
const newsFeed = document.querySelector('#news-feed');
let heroAdvanceLocked = false;

const advancePastHero = (event) => {
  if (
    !cityHero
    || !newsFeed
    || event.deltaY <= 0
    || window.scrollY >= newsFeed.offsetTop - 2
    || document.body.classList.contains('menu-open')
  ) return;

  event.preventDefault();
  if (heroAdvanceLocked) return;
  heroAdvanceLocked = true;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollTo({
    top: newsFeed.offsetTop,
    behavior: reducedMotion ? 'auto' : 'smooth',
  });
  window.setTimeout(() => { heroAdvanceLocked = false; }, reducedMotion ? 100 : 750);
};

if (cityHero && newsFeed) {
  window.addEventListener('wheel', advancePastHero, { passive: false });
}

const deferredImages = document.querySelectorAll('img[data-deferred-src]');
const loadDeferredImage = (image) => {
  image.src = image.dataset.deferredSrc;
  image.removeAttribute('data-deferred-src');
};

if ('IntersectionObserver' in window) {
  const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      loadDeferredImage(entry.target);
      observer.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px 160px' });
  deferredImages.forEach((image) => imageObserver.observe(image));
} else {
  deferredImages.forEach(loadDeferredImage);
}
