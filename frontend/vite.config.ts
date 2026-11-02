import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// SPA: semua route dirender di klien, data diambil dari API Express.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		// Transformasi modul route sejak server start, bukan saat route pertama diklik (hanya mode dev).
		warmup: {
			clientFiles: ['./src/routes/**/+page.svelte', './src/routes/+layout.svelte', './src/lib/components/AppShell.svelte']
		},
		// Saat VITE_USE_MOCK=false, request /api diteruskan ke backend Express.
		proxy: {
			'/api': 'http://localhost:3000'
		}
	}
});
