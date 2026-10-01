// Count the selected interval after the content is visible. Loading and video progress
// have a watchdog so a broken file cannot stop the playlist.
export class BroadcastPlayback {
  constructor(clock = () => performance.now()) {
    this.clock = clock; this.paused = false; this.phase = 'idle';
    this.duration = 5; this.remaining = 5000; this.deadline = Infinity;
  }
  setDuration(seconds) { this.duration = Number(seconds) === 10 ? 10 : 5; }
  loading() { this.phase = 'loading'; this.deadline = this.clock() + 60000; }
  visible() { this.phase = 'visible'; this.remaining = this.duration * 1000; this.deadline = this.clock() + this.remaining; }
  failed() { this.visible(); this.phase = 'failed'; }
  videoProgress() { this.phase = 'video'; this.deadline = this.clock() + 20000; }
  setPaused(value) {
    if (value === this.paused) return;
    if (value) this.remaining = Math.max(0, this.deadline - this.clock());
    else this.deadline = this.clock() + this.remaining;
    this.paused = value;
  }
  due() { return !this.paused && this.clock() >= this.deadline; }
}
