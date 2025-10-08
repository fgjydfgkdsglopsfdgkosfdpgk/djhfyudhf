document.addEventListener('DOMContentLoaded', () => {
  window.__siteLoaded = 'site1';
  const banner = document.createElement('div');
  banner.id = 'site1-status';
  banner.textContent = 'Site1 script ready';
  document.body.appendChild(banner);
});
