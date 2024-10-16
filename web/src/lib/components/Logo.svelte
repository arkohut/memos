<script lang="ts">
	import { generateMemosLogo } from '$lib/logoGenerator';

	export let size = 32;
	export let class_ = '';
	export let withBorder = true;
	export let hasGap = true;

	$: logoSvg = generateMemosLogo(size, withBorder, hasGap);
</script>

<div class={`${class_}`}>
	{@html logoSvg}
</div>
