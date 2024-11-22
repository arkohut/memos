<script lang="ts">
	import '../i18n';
	import '../app.css';
	import { Toaster } from '$lib/components/ui/sonner';
</script>

<svelte:head>
	<title>Pensieve</title>
</svelte:head>

<Toaster />

<div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
	<slot />
</div>
