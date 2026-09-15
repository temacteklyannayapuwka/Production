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

const homeHeaderNav = document.querySelector('.home-page-body .header-nav');
const homeHeaderLinks = homeHeaderNav ? [...homeHeaderNav.querySelectorAll('a')] : [];
let headerFitFramePending = false;

function fitHeaderNavigation() {
  if (!homeHeaderNav) return;
  homeHeaderLinks.forEach((link) => { link.hidden = false; });
  if (window.innerWidth <= 1040) {
    homeHeaderNav.style.removeProperty('width');
    homeHeaderNav.style.removeProperty('max-width');
    return;
  }

  const darkLayerBoundary = window.innerWidth * 0.409375;
  const navigationLeft = homeHeaderNav.getBoundingClientRect().left;
  const availableWidth = Math.max(0, Math.floor(darkLayerBoundary - navigationLeft - 18));
  homeHeaderNav.style.width = `${availableWidth}px`;
  homeHeaderNav.style.maxWidth = `${availableWidth}px`;

  for (let index = homeHeaderLinks.length - 1; index >= 0; index -= 1) {
    if (homeHeaderNav.scrollWidth <= homeHeaderNav.clientWidth) break;
    homeHeaderLinks[index].hidden = true;
  }
}

function scheduleHeaderNavigationFit() {
  if (headerFitFramePending) return;
  headerFitFramePending = true;
  window.requestAnimationFrame(() => {
    fitHeaderNavigation();
    headerFitFramePending = false;
  });
}

fitHeaderNavigation();
document.fonts?.ready.then(fitHeaderNavigation);
window.addEventListener('resize', scheduleHeaderNavigationFit, { passive: true });

const heroCarousel = document.querySelector('[data-hero-carousel]');
const heroSlides = heroCarousel ? [...heroCarousel.querySelectorAll('[data-hero-slide]')] : [];
const heroCopies = heroCarousel ? [...heroCarousel.querySelectorAll('[data-hero-copy]')] : [];
const heroPager = heroCarousel?.querySelector('[data-hero-pager]');
const heroPagerSteps = heroPager ? [...heroPager.querySelectorAll('[data-hero-page]')] : [];
const heroCurrent = heroPager?.querySelector('[data-hero-current]');
const heroTotal = heroPager?.querySelector('[data-hero-total]');
let heroSlideIndex = 0;
let heroCarouselTimer;
let heroCarouselStartedAt = 0;
let heroCarouselRemaining = 7000;
const heroCarouselDuration = 7000;

function renderHeroSlide(nextIndex) {
  if (heroSlides.length < 2) return;
  const normalizedIndex = (nextIndex + heroSlides.length) % heroSlides.length;

  heroSlides.forEach((slide, index) => {
    slide.classList.toggle('is-active', index === normalizedIndex);
    slide.classList.toggle('is-before', index < normalizedIndex);
    slide.setAttribute('aria-hidden', String(index !== normalizedIndex));
  });
  heroCopies.forEach((copy, index) => {
    copy.classList.toggle('is-active', index === normalizedIndex);
    copy.classList.toggle('is-before', index < normalizedIndex);
  });
  heroPagerSteps.forEach((step, index) => {
    step.classList.toggle('is-active', index === normalizedIndex);
    if (index === normalizedIndex) step.setAttribute('aria-current', 'true');
    else step.removeAttribute('aria-current');
  });
  if (heroCurrent) heroCurrent.textContent = String(normalizedIndex + 1).padStart(2, '0');
  if (heroTotal) heroTotal.textContent = String(heroSlides.length).padStart(2, '0');
  heroCarousel?.style.setProperty('--slide-accent', heroSlides[normalizedIndex].dataset.accent || '#f5c518');
  heroSlideIndex = normalizedIndex;
}

function stopHeroCarousel() {
  window.clearTimeout(heroCarouselTimer);
  if (heroCarouselStartedAt) {
    heroCarouselRemaining = Math.max(0, heroCarouselRemaining - (performance.now() - heroCarouselStartedAt));
  }
  heroCarouselStartedAt = 0;
  heroCarousel?.classList.add('is-carousel-paused');
}

function startHeroCarousel(reset = false) {
  window.clearTimeout(heroCarouselTimer);
  if (reset) heroCarouselRemaining = heroCarouselDuration;
  if (heroSlides.length < 2 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  heroCarousel?.classList.remove('is-carousel-paused');
  heroCarouselStartedAt = performance.now();
  heroCarouselTimer = window.setTimeout(() => {
    heroCarouselStartedAt = 0;
    renderHeroSlide(heroSlideIndex + 1);
    startHeroCarousel(true);
  }, heroCarouselRemaining);
}

if (heroSlides.length > 1) {
  renderHeroSlide(0);
  startHeroCarousel(true);
  heroPagerSteps.forEach((step) => step.addEventListener('click', () => {
    const nextIndex = Number(step.dataset.heroPage);
    const changed = nextIndex !== heroSlideIndex;
    if (changed) renderHeroSlide(nextIndex);
    startHeroCarousel(changed);
  }));
  heroPager?.addEventListener('pointerenter', stopHeroCarousel);
  heroPager?.addEventListener('pointerleave', startHeroCarousel);
  heroCarousel?.addEventListener('focusin', stopHeroCarousel);
  heroCarousel?.addEventListener('focusout', startHeroCarousel);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopHeroCarousel();
    else startHeroCarousel();
  });
}

document.querySelectorAll('[data-article-gallery]').forEach((gallery) => {
  const viewport = gallery.querySelector('[data-gallery-viewport]');
  const slides = [...gallery.querySelectorAll('[data-gallery-slide]')];
  const controls = gallery.querySelector('[data-gallery-controls]');
  const previous = gallery.querySelector('[data-gallery-previous]');
  const next = gallery.querySelector('[data-gallery-next]');
  const current = gallery.querySelector('[data-gallery-current]');
  const total = gallery.querySelector('[data-gallery-total]');
  const stepsContainer = gallery.querySelector('[data-gallery-steps]');
  let activeIndex = Math.max(0, slides.findIndex((slide) => slide.classList.contains('is-active')));
  let pointerStartX = null;
  let pointerStartY = null;

  if (total) total.textContent = String(slides.length).padStart(2, '0');
  if (slides.length < 2) {
    if (controls) controls.hidden = true;
    slides[0]?.setAttribute('aria-hidden', 'false');
    fitArticleGalleryToSlide(slides[0]);
    return;
  }

  const steps = slides.map((slide, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', `Показать фотографию ${index + 1}`);
    button.addEventListener('click', () => renderArticleGallery(index));
    stepsContainer?.append(button);
    return button;
  });

  function fitArticleGalleryToSlide(slide) {
    const image = slide?.querySelector('img');
    if (!viewport || !image) return;
    const applyRatio = () => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      viewport.style.aspectRatio = `${image.naturalWidth} / ${image.naturalHeight}`;
    };
    if (image.complete) applyRatio();
    else image.addEventListener('load', applyRatio, { once: true });
  }

  function renderArticleGallery(nextIndex) {
    activeIndex = (nextIndex + slides.length) % slides.length;
    slides.forEach((slide, index) => {
      slide.classList.toggle('is-active', index === activeIndex);
      slide.classList.toggle('is-before', index < activeIndex);
      slide.setAttribute('aria-hidden', String(index !== activeIndex));
    });
    steps.forEach((step, index) => {
      step.classList.toggle('is-active', index === activeIndex);
      if (index === activeIndex) step.setAttribute('aria-current', 'true');
      else step.removeAttribute('aria-current');
    });
    if (current) current.textContent = String(activeIndex + 1).padStart(2, '0');
    fitArticleGalleryToSlide(slides[activeIndex]);
  }

  previous?.addEventListener('click', () => renderArticleGallery(activeIndex - 1));
  next?.addEventListener('click', () => renderArticleGallery(activeIndex + 1));
  viewport?.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    renderArticleGallery(activeIndex + (event.key === 'ArrowRight' ? 1 : -1));
  });
  viewport?.addEventListener('pointerdown', (event) => {
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
  }, { passive: true });
  viewport?.addEventListener('pointerup', (event) => {
    if (pointerStartX === null || pointerStartY === null) return;
    const deltaX = event.clientX - pointerStartX;
    const deltaY = event.clientY - pointerStartY;
    pointerStartX = null;
    pointerStartY = null;
    if (Math.abs(deltaX) < 45 || Math.abs(deltaX) <= Math.abs(deltaY)) return;
    renderArticleGallery(activeIndex + (deltaX < 0 ? 1 : -1));
  }, { passive: true });

  renderArticleGallery(activeIndex);
});

const cityHero = document.querySelector('.city-hero');
const newsFeed = document.querySelector('#news-feed');

function updateHeroSnapScope() {
  if (!cityHero || !newsFeed) return;
  const withinHeroTransition = window.scrollY <= newsFeed.offsetTop + 2;
  document.documentElement.classList.toggle('hero-snap-enabled', withinHeroTransition);
}

updateHeroSnapScope();

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
    updateHeroSnapScope();
    scrollFramePending = false;
  });
}, { passive: true });

backToTop?.addEventListener('click', () => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
});
updateBackToTop();

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
