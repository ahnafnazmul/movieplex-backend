export default async function handler(req, res) {
    const { url } = req.query;
    if (!url) {
        return res.status(400).json({ error: 'URL is required' });
    }

    try {
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://www.moviebox.ph/'
            }
        });

        // সিডিএন-এর হেডারগুলো ফরোয়ার্ড করা
        res.setHeader('Content-Type', response.headers.get('content-type') || 'video/mp4');
        
        const buffer = Buffer.from(await response.arrayBuffer());
        return res.status(200).send(buffer);
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
}
