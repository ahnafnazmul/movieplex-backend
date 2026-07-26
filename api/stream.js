const axios = require('axios');
const crypto = require('crypto');

const SECRET_KEY_DEFAULT = "76iRl07s0xSN9jqmEWAt79EBJZulIQIsV64FZr2O";
const HOST_POOL = [
    "https://api6.aoneroom.com", "https://api5.aoneroom.com", "https://api4.aoneroom.com",
    "https://api4sg.aoneroom.com", "https://api3.aoneroom.com", "https://api6sg.aoneroom.com",
    "https://api.inmoviebox.com"
];

let currentHostIdx = 0;
let runtimeToken = null;

function generateSpoofedIp() {
    const prefixes = ["103.241", "49.36", "117.195", "106.198", "122.162", "157.32", "182.70", "103.58", "27.60", "59.90"];
    const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
    return `${prefix}.${Math.floor(Math.random() * 253) + 1}.${Math.floor(Math.random() * 253) + 1}`;
}
const spoofedIp = generateSpoofedIp();

function generateXClientToken(ts) {
    const reversedTs = ts.toString().split('').reverse().join('');
    return `${ts},${crypto.createHash('md5').update(reversedTs).digest('hex')}`;
}

function getSortedQueryString(fullUrl) {
    if (!fullUrl.includes('?')) return '';
    const params = new URLSearchParams(fullUrl.split('?')[1]);
    return Array.from(params.keys()).sort().map(key => params.getAll(key).map(val => `${key}=${val}`).join('&')).join('&');
}

function generateSignature(method, fullUrl, body = '', ts) {
    const canonicalUrl = fullUrl.includes('?') ? `${new URL(fullUrl).pathname}?${getSortedQueryString(fullUrl)}` : new URL(fullUrl).pathname;
    let bodyHash = '', bodyLength = '';
    if (body) {
        bodyLength = Buffer.byteLength(body).toString();
        bodyHash = crypto.createHash('md5').update(body.substring(0, 102400)).digest('hex');
    }
    const canonical = `${method.toUpperCase()}\napplication/json\napplication/json\n${bodyLength}\n${ts}\n${bodyHash}\n${canonicalUrl}`;
    return `${ts}|2|${crypto.createHmac('md5', Buffer.from(SECRET_KEY_DEFAULT, 'base64')).update(canonical).digest('base64')}`;
}

function getHeaders(method, fullUrl, body = '') {
    const ts = Date.now();
    const headers = {
        'User-Agent': 'com.community.oneroom/50020045 (Linux; U; Android 13; en_US; Redmi Build/TQ2A.230405.003; Cronet/135.0.7012.3)',
        'Accept': 'application/json', 'Content-Type': 'application/json', 'Connection': 'keep-alive',
        'X-Client-Token': generateXClientToken(ts), 'x-tr-signature': generateSignature(method, fullUrl, body ? JSON.stringify(body) : '', ts),
        'X-Client-Info': `{"package_name":"com.community.oneroom","version_name":"3.0.03.0529.03","version_code":50020045,"os":"android","os_version":"13","device_id":"5c7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c","brand":"Redmi","model":"23078RKD5C","net":"NETWORK_WIFI","region":"BD","timezone":"Asia/Dhaka"}`,
        'X-Client-Status': '0', 'X-Forwarded-For': spoofedIp
    };
    if (runtimeToken) headers['Authorization'] = `Bearer ${runtimeToken}`;
    return headers;
}

async function makeRequest(method, path, body = null) {
    for (let i = 0; i < HOST_POOL.length; i++) {
        const idx = (currentHostIdx + i) % HOST_POOL.length;
        const url = `${HOST_POOL[idx]}${path}`;
        try {
            const headers = getHeaders(method, url, body);
            const res = method === 'POST' ? await axios.post(url, body, { headers, timeout: 8000 }) : await axios.get(url, { headers, timeout: 8000 });
            if (res.headers['x-user']) {
                const token = JSON.parse(res.headers['x-user']).token;
                if (token) runtimeToken = token;
            }
            if (res.status === 403 || res.data?.code === 403) continue;
            currentHostIdx = idx;
            return res.data;
        } catch (err) { continue; }
    }
    throw new Error("All MovieBox API hosts rejected the request.");
}

// এই অংশটি ভার্সেল হ্যান্ডলারের জন্য স্পেশাল
module.exports = async (req, res) => {
    // CORS পলিসি সেট করা (যাতে আপনার ফ্রন্টএন্ড থেকে সহজে ডেটা আনা যায়)
    res.setHeader('Access-Control-Allow-Credentials', true);
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    const movieName = req.query.q;
    if (!movieName) {
        return res.status(400).json({ error: "Movie name is required. Example: ?q=Alpha 2026" });
    }

    try {
        await makeRequest('GET', "/wefeed-mobile-bff/tab-operating?page=1&tabId=0&version=");
        
        const searchData = await makeRequest('POST', "/wefeed-mobile-bff/subject-api/search/v2", { keyword: movieName, page: 1, perPage: 20, subjectType: "All", tabId: "All" });
        const results = searchData?.results || searchData?.data?.results || [];
        let firstMovie = results.find(r => r.topicType === "SUBJECT" && r.subjects?.length > 0)?.subjects[0];

        if (!firstMovie) {
            return res.status(404).json({ error: "No movie found." });
        }

        const subjectId = firstMovie.subjectId || firstMovie.id;
        const resData = await makeRequest('GET', `/wefeed-mobile-bff/subject-api/resource?subjectId=${subjectId}&page=1&perPage=20`);
        const resources = resData?.list || resData?.data?.list || [];

        const links = resources.map(item => ({
            quality: `${item.resolution || item.quality || "Unknown"}p`,
            url: item.resourceLink || item.code || item.url || item.playUrl
        }));

        return res.status(200).json({
            title: firstMovie.title,
            releaseDate: firstMovie.releaseDate,
            streams: links
        });

    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
};