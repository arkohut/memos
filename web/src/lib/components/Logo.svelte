<script lang="ts">
	function seededRandom(seed: number): number {
		let x = Math.sin(seed++) * 10000;
		return x - Math.floor(x);
	}

	export let size = 32;
	export let class_ = '';
	export let withBorder = true;

	function prepareMatrixFromRandomColors(withBorder: boolean): string[][] {
        const colors = ['#d0e8ff', '#a1d2ff', '#64b5f6', '#1565c0', '#0d47a1'];
		const mShape = withBorder
			? [
					[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
					[0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0],
					[0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0],
					[0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0],
					[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
			  ]
			: [
					[1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
					[1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
					[1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1],
					[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
					[1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1],
					[1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1]
			  ];

		const gridSize = withBorder ? 13 : 11;
		let seed = 42;
		const matrix: string[][] = [];

		for (let row = 0; row < gridSize; row++) {
			const rowColors: string[] = [];
			for (let col = 0; col < gridSize; col++) {
				let colorIndex;
				if (mShape[row][col] === 1) {
					colorIndex = Math.floor(seededRandom(seed++) * 2) + 3;
				} else {
					colorIndex = Math.floor(seededRandom(seed++) * 3);
				}
				rowColors.push(colors[colorIndex]);
			}
			matrix.push(rowColors);
		}

		return matrix;
	}

	function generateSvg(matrix: string[][], size: number): string {
		const gridSize = matrix.length;
		const cellSize = 1;
		const rectSize = 0.85;

		let svgContent = `<svg width="${size}" height="${size}" viewBox="0 0 ${gridSize} ${gridSize}" xmlns="http://www.w3.org/2000/svg" opacity="1">
`;

		for (let row = 0; row < gridSize; row++) {
			for (let col = 0; col < gridSize; col++) {
				svgContent += `  <rect x="${col * cellSize + 0.075}" y="${
					row * cellSize + 0.075
				}" width="${rectSize}" height="${rectSize}" rx="0.15" ry="0.15" fill="${matrix[row][col]}" />
`;
			}
		}

		svgContent += `</svg>`;
		return svgContent;
	}

	function generateMemosLogo(size: number, withBorder: boolean): string {
		const matrix = prepareMatrixFromRandomColors(withBorder);
		return generateSvg(matrix, size);
	}

	$: logoSvg = generateMemosLogo(size, withBorder);
</script>

<div class={`${class_}`}>
	{@html logoSvg}
</div>
