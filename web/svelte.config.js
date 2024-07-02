import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			pages: '../build',
			assets: '../build',
			precompress: false,
			strict: true,
			fallback: 'app.html' // may differ from host to host
		})
	}
};

export default config;
