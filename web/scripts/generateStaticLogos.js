import fs from 'fs';
import path from 'path';
import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { generateMemosLogo } from './logoGenerator.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);


async function generatePNGLogo(size, outputFileName) {
    let svgContent;
    if (size <= 256) {
        svgContent = generateMemosLogo(size, false, false);
    } else {
        svgContent = generateMemosLogo(size, true, true);
    }

    // 确保 logos 目录存在
    const logosDir = path.join(__dirname, '..', 'static', 'logos');
    if (!fs.existsSync(logosDir)) {
        fs.mkdirSync(logosDir, { recursive: true });
    }

    const outputPath = path.join(logosDir, outputFileName);

    await sharp(Buffer.from(svgContent))
        .png()
        .toFile(outputPath);
}

// Mac app icon sizes
const iconSizes = [16, 32, 64, 128, 256, 512, 1024];

// Generate logos for each size
(async () => {
    for (const size of iconSizes) {
        await generatePNGLogo(size, `memos_logo_${size}.png`);
        // Generate @2x version for Retina displays
        await generatePNGLogo(size * 2, `memos_logo_${size}@2x.png`);
    }
    console.log('PNG logos generated successfully in the static/logos directory!');

    // Copy 128x128 logo to static/favicon.png
    const sourceFile = path.join(__dirname, '..', 'static', 'logos', 'memos_logo_128.png');
    const destinationFile = path.join(__dirname, '..', 'static', 'favicon.png');
    
    fs.copyFile(sourceFile, destinationFile, (err) => {
        if (err) {
            console.error('Error copying favicon:', err);
        } else {
            console.log('Favicon copied successfully to static/favicon.png');
        }
    });
})();
