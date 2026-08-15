// gd-sprite.js
// Swaps the Chrome dinosaur for the Glow Daze mascot.
// Load AFTER index.js and BEFORE the game starts.
//
// The mascot lives in its own sprite sheet rather than being composited into
// the Chrome one, so Laayba can redraw her without anyone rebuilding a sheet.
// Every cell is the same size and bottom-anchored, which is what makes ducking
// work: the crouch art is simply shorter inside its cell, so drawing all cells
// identically puts her lower with no separate duck geometry.
//
// Frames: 0-5 run, 6-7 duck, 8 crash. Generated from OG.png by
// scratchpad/build_sheet.py -- see assets/GD/glowdaze-sheet.json.

(function () {
    'use strict';

    var SHEET_1X = 'assets/GD/glowdaze-sheet.png';
    var SHEET_2X = 'assets/GD/glowdaze-sheet-2x.png';

    // The cell is taller than the dino's 47 because it has to hold her bounce.
    // That is safe: the engine draws the cell from yPos to yPos + HEIGHT, and
    // groundYPos is 150 - HEIGHT - 10, so the cell's bottom edge lands on y=140
    // whatever the height. Ground contact does not move; the cell just grows up.
    var CELL_W = 47, CELL_H = 50;          // drawn size, and the 1x cell size
    var CELL2X_W = 94, CELL2X_H = 100;

    var RUN = [0, 1, 2, 3, 4, 5];
    var DUCK = [6, 7];
    var CRASH = 8;
    var STAND = 0;

    // 420 ms for the whole stride, which is the pace that read best against
    // the ground scrolling at the runner's opening speed.
    var RUN_MS = 420 / RUN.length;

    // Boxes traced from her actual silhouette, in drawn pixels relative to the
    // top-left of her cell. The dino's were shaped like a dinosaur: a tall head
    // over a narrow body. Hers is a long horizontal leap with a trailing tail.
    var COLLISION = {
        RUNNING: [[0, 18, 12, 28], [12, 15, 12, 30], [24, 0, 12, 44], [35, 0, 12, 39]],
        DUCKING: [[0, 28, 16, 22], [16, 18, 16, 32], [31, 20, 16, 26]]
    };

    var isHiDPI = window.devicePixelRatio > 1;
    var sheet = new Image();
    var sheetReady = false;

    sheet.onload = function () { sheetReady = true; };
    sheet.onerror = function () {
        console.error('[gd-sprite] could not load the mascot sheet; ' +
                      'the game will keep running as the dinosaur.');
    };
    sheet.src = isHiDPI ? SHEET_2X : SHEET_1X;

    function patch() {
        var Trex = window.Trex;
        if (!Trex || !Trex.config || !Trex.animFrames) {
            return false;
        }

        // Same height as the dinosaur, so her ground position needs no change.
        Trex.config.WIDTH = CELL_W;
        Trex.config.HEIGHT = CELL_H;
        Trex.config.WIDTH_DUCK = CELL_W;   // cells are uniform; ducking uses the same box

        // Six frames instead of the dino's two. Overriding draw removes the
        // engine's two-frame limit, so her gait is smoother than the original.
        Trex.animFrames.WAITING.frames = [STAND];
        Trex.animFrames.RUNNING.frames = RUN;
        Trex.animFrames.RUNNING.msPerFrame = RUN_MS;
        Trex.animFrames.JUMPING.frames = [STAND];
        Trex.animFrames.CRASHED.frames = [CRASH];
        Trex.animFrames.DUCKING.frames = DUCK;

        Trex.collisionBoxes.RUNNING = COLLISION.RUNNING.map(toBox);
        Trex.collisionBoxes.DUCKING = COLLISION.DUCKING.map(toBox);

        // update() passes whatever is in animFrames straight to draw(), so the
        // first argument arrives as a cell index rather than a pixel offset.
        Trex.prototype.draw = function (frameIndex, _y) {
            if (!sheetReady) {
                return;
            }
            var sw = isHiDPI ? CELL2X_W : CELL_W;
            var sh = isHiDPI ? CELL2X_H : CELL_H;
            this.canvasCtx.drawImage(
                sheet,
                frameIndex * sw, 0, sw, sh,
                Math.round(this.xPos), Math.round(this.yPos), CELL_W, CELL_H);
        };

        // The dino blinks by swapping to a second idle frame. She has one idle
        // pose, so blinking would just redraw the same pixels -- draw once and
        // skip the timer entirely.
        Trex.prototype.blink = function () {
            this.draw(STAND, 0);
        };

        return true;
    }

    function toBox(b) {
        // CollisionBox is private to index.js, but the engine only ever reads
        // .x/.y/.width/.height off these, so a plain object is equivalent.
        return { x: b[0], y: b[1], width: b[2], height: b[3] };
    }

    // index.js builds the Trex statics as it evaluates, and this file loads
    // after it, so one pass is normally enough. Retry briefly in case script
    // ordering changes.
    if (!patch()) {
        var tries = 0;
        var timer = setInterval(function () {
            if (patch() || ++tries > 40) {
                clearInterval(timer);
                if (tries > 40) {
                    console.error('[gd-sprite] window.Trex never appeared; ' +
                                  'is gd-sprite.js loaded after index.js?');
                }
            }
        }, 50);
    }
})();
