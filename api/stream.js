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

// ভার্সেল ডেটাসেন্টার লুকাতে আরও উন্নত র্যান্ডম এশিয়ান আইপি জেনারেটর
function generateSpoofedIp() {
    const prefixes = ["103.241.130", "49.36.45", "117.195.88", "106.198.12", "122.162.90", "27.60.11", "103.58.40"];
    const prefix = prefixes[Math.floor(Math.random() * prefixes.length)];
    return `${prefix}.${Math.floor(Math.random() * 250) + 2}`;
}

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
    const currentIp = generateSpoofedIp();
    const headers = {
        'User-Agent': 'com.community.oneroom/50020045 (Linux; U; Android 13; en_US; Redmi Build/TQ2A.230405.003; Cronet/135.0.7012.3)',
        'Accept': 'application/json', 
        'Content-Type': 'application/json', 
        'Connection': 'keep-alive',
        'X-Client-Token': generateXClientToken(ts), 
        'x-tr-signature': generateSignature(method, fullUrl, body ? JSON.stringify(body) : '', ts),
        'X-Client-Info': `{"package_name":"com.community.oneroom","version_name":"3.0.03.0529.03","version_code":50020045,"os":"android","os_version":"13","device_id":"5c7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c","brand":"Redmi","model":"23078RKD5C","net":"NETWORK_WIFI","region":"BD","timezone":"Asia/Dhaka"}`,
        'X-Client-Status': '0',
        // ভার্সেল প্রক্সি বাইপাস করার জন্য ৩ লেভেলের আইপি মাস্কিং হেডার
        'X-Forwarded-For': currentIp,
        'Client-Ip': currentIp,
        'X-Real-Ip': currentIp
    };
    if (runtimeToken) headers['Authorization'] = `Bearer ${runtimeToken}`;
    return headers;
}

async function makeRequest(method, path, body = null) {
    let lastError = "";
    for (let i = 0; i < HOST_POOL.length; i++) {
        const idx = (currentHostIdx + i) % HOST_POOL.length;
        const url = `${HOST_POOL[idx]}${path}`;
        try {
            const headers = getHeaders(method, url, body);
            const res = method === 'POST' ? 
                await axios.post(url, body, { headers, timeout: 9000 }) : 
                await axios.get(url, { headers, timeout: 9000 });
                
            if (res.headers['x-user']) {
                const token = JSON.parse(res.headers['x-user']).token;
                if (token) runtimeToken = token;
            }
            if (res.status === 403 || res.data?.code === 403 || res.data?.code === 401) {
                lastError = `Host ${HOST_POOL[idx]} returned auth/permission error.`;
                continue;
            }
            currentHostIdx = idx;
            return res.data;
        } catch (err) { 
            lastError = err.message;
            continue; 
        }
    }
    throw new Error(`MovieBox API Connection Failed. Detail: ${lastError}`);
}

module.exports = async (req, res) => {
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
            return res.status(404).json({ error: `No movie found for query: ${movieName}` });
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
