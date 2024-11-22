function seededRandom(seed) {
    let x = Math.sin(seed++) * 10000;
    return x - Math.floor(x);
}

function prepareMatrixFromFixedIndexAndLittleRadom(withBorder) {
    const bgColors = ['#f2f2f2', '#e9e9e9', '#d8d8d8']
    // const colors = ['#d0e8ff', '#F2295F', '#E0A0F2', '#F2B705'];
    const colors = ['#d0e8ff', '#BF244E', '#8C2685', '#21A650'];
    const mShape = withBorder
        ? [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0, 0],
                [0, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 0, 0],
                [0, 1, 1, 1, 2, 0, 0, 0, 2, 3, 3, 3, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3, 0],
                [0, 1, 1, 1, 2, 0, 0, 0, 2, 3, 3, 3, 0],
                [0, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 0, 0],
                [0, 1, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
          ]
        : [
                [0, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0],
                [1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 0],
                [1, 1, 1, 2, 0, 0, 0, 2, 3, 3, 3],
                [1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3],
                [1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3],
                [1, 1, 1, 0, 0, 0, 0, 0, 3, 3, 3],
                [1, 1, 1, 2, 0, 0, 0, 2, 3, 3, 3],
                [1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 0],
                [1, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0],
                [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
          ];

    const gridSize = withBorder ? 13 : 11;
    let seed = 42;
    const matrix = [];

    for (let row = 0; row < gridSize; row++) {
        const rowColors = [];
        const bgSize = bgColors.length;
        for (let col = 0; col < gridSize; col++) {
            if (mShape[row][col] === 0) {
                rowColors.push(bgColors[Math.floor(seededRandom(seed++) * bgSize)]);
            } else {
                rowColors.push(colors[mShape[row][col]]);
            }
        }
        matrix.push(rowColors);
    }

    return matrix;
}

function prepareMatrixFromRandomColors(withBorder) {
    const colors = ['#d0e8ff', '#a1d2ff', '#64b5f6', '#1565c0', '#0d47a1'];
    const mShape = withBorder
        ? [
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
                [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
                [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0],
                [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0],
                [0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
          ]
        : [
                [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
                [1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
                [1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
                [1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
                [1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
                [1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
                [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0],
                [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
          ];

    const gridSize = withBorder ? 13 : 11;
    let seed = 42;
    const matrix = [];

    for (let row = 0; row < gridSize; row++) {
        const rowColors = [];
        for (let col = 0; col < gridSize; col++) {
            let colorIndex;
            if (mShape[row][col] === 1) {
                colorIndex = Math.floor(seededRandom(seed++) * 2) + 3;
            } else {
                colorIndex = Math.floor(seededRandom(seed++) * 2);
            }
            rowColors.push(colors[colorIndex]);
        }
        matrix.push(rowColors);
    }

    return matrix;
}

function generateSvg(matrix, size, hasGap) {
    const gridSize = matrix.length;
    const cellSize = 1;
    const rectSize = hasGap ? 0.85 : 1;
    const offset = hasGap ? 0.075 : 0;

    let svgContent = `<svg width="${size}" height="${size}" viewBox="0 0 ${gridSize} ${gridSize}" xmlns="http://www.w3.org/2000/svg" opacity="1">
`;

    for (let row = 0; row < gridSize; row++) {
        for (let col = 0; col < gridSize; col++) {
            svgContent += `  <rect x="${col * cellSize + offset}" y="${
                row * cellSize + offset
            }" width="${rectSize}" height="${rectSize}" rx="${hasGap ? 0.15 : 0}" ry="${hasGap ? 0.15 : 0}" fill="${matrix[row][col]}" />
`;
        }
    }

    svgContent += `</svg>`;
    return svgContent;
}

export function generateMemosLogo(size, withBorder, hasGap) {
    const matrix = prepareMatrixFromRandomColors(withBorder);
    return generateSvg(matrix, size, hasGap);
}

