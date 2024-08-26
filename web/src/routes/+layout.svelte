<script lang="ts">
	import '../app.css';
	import { Toaster } from "$lib/components/ui/sonner";
</script>

<Toaster />

<div class="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
	<slot />
</div>
