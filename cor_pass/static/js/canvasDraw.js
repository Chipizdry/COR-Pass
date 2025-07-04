let ctxOptions = {}
let history = [];

const revertDraw = (e) => {
    const {canvasWidth, canvasHeight, ctx} = ctxOptions

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (history.length > 0) {
            const last = history.pop();
            ctx.clearRect(0, 0, canvasWidth, canvasHeight);
            ctx.putImageData(last, 0, 0);
        }
    }
}

const drawHandlers = (canvasNode) => {
    let drawing = false;
    const {dpr, canvasWidth, canvasHeight, ctx} = ctxOptions

    const getMousePositionOnCanvas = (e) => {
        const rect = canvasNode.getBoundingClientRect();
        return {
            x: (e.clientX - rect.left) * (canvasNode.width / rect.width) / dpr,
            y: (e.clientY - rect.top) * (canvasNode.height / rect.height) / dpr
        };
    }

    const saveState = () => {
        const snapshot = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
        history.push(snapshot);
        if (history.length > 100) history.shift();
    }

    canvasNode.addEventListener('mousedown', (e) => {
        saveState(); // Save BEFORE drawing
        drawing = true;
        const { x, y } = getMousePositionOnCanvas(e);
        ctx.beginPath();
        ctx.moveTo(x, y);
    });

    canvasNode.addEventListener('mousemove', (e) => {
        if (!drawing) return;
        const { x, y } = getMousePositionOnCanvas(e);
        ctx.lineTo(x, y);
        ctx.stroke();
    });

    canvasNode.addEventListener('mouseup', () => {
        drawing = false;
    });

    canvasNode.addEventListener('mouseleave', () => {
        drawing = false;
    });

    window.addEventListener('keydown', revertDraw);
}

const drawClear = () => {
    const { ctx, canvasWidth, canvasHeight} = ctxOptions;
    ctx?.clearRect(0, 0, canvasWidth, canvasHeight);
    history = []
}

const drawDestroy = () => {
    window.removeEventListener('keydown', revertDraw);
    drawClear();
    ctxOptions = {};
}

const drawInit = (canvasNode, options) => {
    const {minWidth, minHeight} = options

    const dpr = window.devicePixelRatio || 1;
    const width = minWidth || canvasNode.clientWidth;
    const height = minHeight;

    const canvasWidth = width * dpr
    const canvasHeight = height * dpr

    ctxOptions = {
        ctx: canvasNode.getContext('2d'),
        dpr,
        canvasWidth,
        canvasHeight,
    }

    const {ctx} = ctxOptions;

    canvasNode.width = canvasWidth;
    canvasNode.height = canvasHeight;
    canvasNode.style.width = width + 'px';
    canvasNode.style.height = height + 'px';
    ctx.scale(dpr, dpr);

    // Drawing settings
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#000';


    drawHandlers(canvasNode)
}
