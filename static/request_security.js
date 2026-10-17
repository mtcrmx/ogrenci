(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  if (!token) return;
  const unsafe = method => !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase());
  const local = url => new URL(url, location.href).origin === location.origin;
  const originalFetch = window.fetch;
  window.fetch = function(input, init = {}) {
    const req = input instanceof Request;
    const method = init.method || (req ? input.method : 'GET');
    if (unsafe(method) && local(req ? input.url : input)) {
      const headers = new Headers(init.headers || (req ? input.headers : undefined));
      headers.set('X-CSRF-Token', token);
      init = {...init, headers};
    }
    return originalFetch.call(this, input, init);
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...args) {
    this.schoolCSRF = unsafe(method) && local(url);
    return open.call(this, method, url, ...args);
  };
  XMLHttpRequest.prototype.send = function(body) {
    if (this.schoolCSRF) this.setRequestHeader('X-CSRF-Token', token);
    return send.call(this, body);
  };
  // Also cover forms created after the initial server render.
  const protectForm = form => {
    if (form.method.toLowerCase() !== 'post' || !local(form.action)) return;
    let field = form.querySelector('[name="_csrf_token"]');
    if (!field) {field = document.createElement('input'); field.type = 'hidden'; field.name = '_csrf_token'; form.append(field);}
    field.value = token;
  };
  document.addEventListener('submit', event => protectForm(event.target), true);
  const submit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function() {protectForm(this); return submit.call(this);};
})();
