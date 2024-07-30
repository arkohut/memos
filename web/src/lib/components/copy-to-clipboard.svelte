<script>
	import { Copy, Check } from 'lucide-svelte';

	export let text;

	let copied = false;

	/**
	 * Copy text to clipboard and change icon
	 * @param {string} text
	 */
	function handleCopyClick(text) {
		navigator.clipboard.writeText(text).then(() => {
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		}).catch(err => {
			console.error('Failed to copy text: ', err);
		});
	}
</script>

<button class="ml-2 flex items-center" on:click={() => handleCopyClick(text)}>
	{#if copied}
		<Check size={20} />
	{:else}
		<Copy size={20} />
	{/if}
</button>