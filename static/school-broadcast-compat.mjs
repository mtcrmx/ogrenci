// PDF.js legacy still assumes Promise.withResolvers (Chrome 124+).
// Keep both the window and worker usable on older school computers.
export function ensurePresentationPromises() {
  if (typeof Promise.withResolvers !== 'function') {
    Object.defineProperty(Promise, 'withResolvers', {
      configurable: true, writable: true,
      value: function () {
        let resolve, reject;
        const promise = new this((res, rej) => { resolve = res; reject = rej; });
        return { promise, resolve, reject };
      }
    });
  }
}
