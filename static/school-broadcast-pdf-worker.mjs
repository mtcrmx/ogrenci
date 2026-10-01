import {ensurePresentationPromises} from './school-broadcast-compat.mjs';
ensurePresentationPromises();
const {WorkerMessageHandler} = await import('./vendor/pdfjs/legacy/build/pdf.worker.min.mjs');
export {WorkerMessageHandler};
