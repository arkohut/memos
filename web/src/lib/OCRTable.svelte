<script>
	/**
	 * @type {Array<{dt_boxes: any, rec_txt: string, score: number}>}
	 */
	export let ocrData = [];
</script>
<table class="min-w-full bg-white">
	<thead>
		<tr>
			<th class="py-2">Text</th>
			<th class="py-2" style="width: 50px;">Score</th>
		</tr>
	</thead>
	<tbody>
		{#each ocrData as { dt_boxes, rec_txt, score }}
			<tr class="hover:bg-gray-100">
				<td class="border px-4 py-2">{rec_txt}</td>
				<td class="border px-4 py-2" style="width: 50px;">{score.toFixed(3)}</td>
			</tr>
		{/each}
	</tbody>
</table>