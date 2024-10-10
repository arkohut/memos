<script>
	/**
	 * @type {Array<{dt_boxes: any, rec_txt: string, score: number}>}
	 */
	export let ocrData = [];
</script>

<div class="overflow-x-auto">
	<table class="w-full max-w-3xl bg-white table-fixed">
		<thead>
			<tr>
				<th class="py-2 w-4/5">Text</th>
				<th class="py-2 w-1/5">Score</th>
			</tr>
		</thead>
		<tbody>
			{#each ocrData as { dt_boxes, rec_txt, score }}
				<tr class="hover:bg-gray-100">
					<td class="border px-4 py-2 truncate">{rec_txt}</td>
					<td class="border px-4 py-2 text-center">{score.toFixed(3)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>