// Player frame-accurate: timecode hh:mm:ss:ff, -1/+1 frame, scrubber theo frame.
(function () {
  document.querySelectorAll('.player').forEach((root) => {
    const video = root.querySelector('video');
    const fps = parseFloat(root.dataset.fps) || 25;
    const nominal = Math.max(Math.round(fps), 1);
    const total = Math.max(Math.round(parseFloat(root.dataset.duration) * fps), 1);
    const tcEl = root.querySelector('.tc');
    const scrub = root.querySelector('input[type=range]');
    const frameEl = root.querySelector('.frame-info');
    scrub.max = total;

    const pad = (n) => String(n).padStart(2, '0');
    const toTc = (frames) => {
      const ff = frames % nominal, s = Math.floor(frames / nominal);
      return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}:${pad(ff)}`;
    };
    const curFrame = () => Math.min(Math.round(video.currentTime * fps), total);
    const update = () => {
      const f = curFrame();
      tcEl.textContent = `${toTc(f)} / ${root.dataset.durationTc}`;
      if (document.activeElement !== scrub) scrub.value = f;
      if (frameEl) frameEl.textContent = `Frame: ${f} / ${total}`;
    };
    const seekFrame = (f) => { video.currentTime = Math.min(Math.max(f, 0), total) / fps; };

    video.addEventListener('timeupdate', update);
    video.addEventListener('seeked', update);
    video.addEventListener('loadedmetadata', update);
    scrub.addEventListener('input', () => { video.pause(); seekFrame(parseInt(scrub.value, 10)); });
    root.querySelector('.prev-frame').addEventListener('click', () => { video.pause(); seekFrame(curFrame() - 1); });
    root.querySelector('.next-frame').addEventListener('click', () => { video.pause(); seekFrame(curFrame() + 1); });
    // proxy loi -> thu file goc
    video.addEventListener('error', () => {
      const alt = root.dataset.original;
      if (alt && !video.dataset.fellBack) { video.dataset.fellBack = '1'; video.src = alt; video.load(); }
    });
    // phim tat: , va . = lui/tien 1 frame; space = play/pause
    root.tabIndex = 0;
    root.addEventListener('keydown', (e) => {
      if (e.key === ',') { video.pause(); seekFrame(curFrame() - 1); }
      else if (e.key === '.') { video.pause(); seekFrame(curFrame() + 1); }
      else if (e.key === ' ') { e.preventDefault(); video.paused ? video.play() : video.pause(); }
    });
    update();
  });
})();
