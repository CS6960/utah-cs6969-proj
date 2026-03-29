import { defineConfig, mergeConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { existsSync } from 'fs'
import { resolve } from 'path'

const baseConfig = defineConfig({
  plugins: [react()],
  base: '/utah-cs6969-proj/',
})

// Load local overrides from vite.config.local.js (gitignored)
let localConfig = {}
const localPath = resolve(__dirname, 'vite.config.local.js')
if (existsSync(localPath)) {
  localConfig = (await import(localPath)).default
}

export default mergeConfig(baseConfig, localConfig)
