<script lang="ts">
	function seededRandom(seed: number): number {
		let x = Math.sin(seed++) * 10000;
		return x - Math.floor(x);
	}

	export let size = 32; // 默认大小为 32
	export let class_ = ''; // 添加一个 class prop，使用 class_ 避免与 JavaScript 关键字冲突
	export let withBorder = true; // 新增参数，默认为 true

	function generateMemosLogo(size: number, withBorder: boolean): string {
		const colors = ['#f0f8ff', '#d0e8ff', '#a1d2ff', '#64b5f6', '#1565c0', '#0d47a1']; // Adjusted colors
		const cellSize = 1; // Set to 1 to make scaling easier
		const rectSize = 0.85; // Slightly smaller than cellSize to create gaps
		let svgContent = '';
		let seed = 42;

		// Define the 'M' shape
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

		// Create the SVG header
		svgContent += `<svg width="${size}" height="${size}" viewBox="0 0 ${gridSize} ${gridSize}" xmlns="http://www.w3.org/2000/svg" opacity="1">
`;

		// Generate grid of cells with rounded corners
		for (let row = 0; row < gridSize; row++) {
			for (let col = 0; col < gridSize; col++) {
				let colorIndex;

				// Define the pattern for the 'M' shape
				if (mShape[row][col] === 1) {
					colorIndex = Math.floor(seededRandom(seed++) * 2) + 4;
				} else {
					colorIndex = Math.floor(seededRandom(seed++) * 3);
				}

				svgContent += `  <rect x="${col * cellSize + 0.075}" y="${
					row * cellSize + 0.075
				}" width="${rectSize}" height="${rectSize}" rx="0.15" ry="0.15" fill="${
					colors[colorIndex]
				}" />
`;
			}
		}

		// Close the SVG tag
		svgContent += `</svg>`;

		// Instead of writing to file, return the SVG content
		return svgContent;
	}

	$: logoSvg = generateMemosLogo(size, withBorder);
</script>

<div class={`${class_}`}>
	{@html logoSvg}
</div>
