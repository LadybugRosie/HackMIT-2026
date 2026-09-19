import { ObjectSchema } from '@eslint/object-schema'

// 默认配置
const defaultOptions = {
  editorKey: 'default',
  locale: 'en-US',
  theme: 'light',
  height: '100%',
  dicts: {
    fonts: [
      { label: { en_US: 'Default Font', zh_CN: '默认字体', ar_KSA: 'الخط الافتراضي', ja_JP: 'デフォルトフォント', ur_IN: 'بنیادی فونٹ', hi_IN: 'डिफ़ॉल्ट फॉन्ट', kn_IN: 'ಡಿಫಾಲ್ಟ್ ಫಾಂಟ್', ta_IN: 'இயல்பு எழுத்துரு', te_IN: 'డిఫాల్ట్ ఫాంట్', sp_SPA: 'Fuente Predeterminada' }, value: null },
      { label: { en_US: 'Songti', zh_CN: '宋体' }, value: 'SimSun' },
      { label: { en_US: 'Heiti', zh_CN: '黑体' }, value: 'SimHei' },
      { label: { en_US: 'Kaiti', zh_CN: '楷体' }, value: 'KaiTi' },
      {
        label: { en_US: 'Kaiti GB2312', zh_CN: '楷体_GB2312' },
        value: 'KaiTi_GB2312',
      },
      { label: { en_US: 'Fangsong', zh_CN: '仿宋' }, value: 'FangSong' },
      {
        label: { en_US: 'Fangsong GB2312', zh_CN: '仿宋_GB2312' },
        value: 'FangSong_GB2312',
      },
      { label: { en_US: 'STSong', zh_CN: '华文宋体' }, value: 'STSong' },
      {
        label: { en_US: 'STFangsong', zh_CN: '华文仿宋' },
        value: 'STFangsong',
      },
      {
        label: { en_US: 'FZ Fangsong Simplified', zh_CN: '方正仿宋简体' },
        value: 'FZFangSong-Z02S',
      },
      {
        label: { en_US: 'FZ Xiaobiao Song', zh_CN: '方正小标宋' },
        value: 'FZXiaoBiaoSong-B05S',
      },
      {
        label: { en_US: 'Microsoft Yahei', zh_CN: '微软雅黑' },
        value: 'Microsoft Yahei',
      },
      { label: 'Arial', value: 'Arial' },
      { label: 'Times New Roman', value: 'Times New Roman' },
      { label: 'Verdana', value: 'Verdana' },
      { label: 'Helvetica', value: 'Helvetica' },
      { label: 'Calibri', value: 'Calibri' },
      { label: 'Cambria', value: 'Cambria' },
      { label: 'Tahoma', value: 'Tahoma' },
      { label: 'Georgia', value: 'Georgia' },
      { label: 'Comic Sans MS', value: 'Comic Sans MS' },
      { label: 'Impact', value: 'Impact' },
    ],
    // prettier-ignore
    colors: [
      '#FFF', '#000', '#4A5366', '#3B74EC', '#45A2EF', '#529867', '#CD4A3F', '#EA8D40', '#EEC543', '#8E45D0', '#F2F2F2', '#7F7F7F', '#F4F5F7', '#CBDCFC', '#E8F6FE', '#EDFAF2', '#FCEAE9', '#FDF3EC', '#FEF9E5', '#FAECFE', '#EEE', '#595959', '#C6CAD2', '#CEEBFD', '#CBDCFC', '#CBE9D7', '#F7CBC9', '#FADDC7', '#FDEEB5', '#EBCAFC', '#BFBFBF', '#3F3F3F', '#828B9D', '#A0BEFA', '#A7DCFC', '#A6D5B8', '#F2A19C', '#F5BC8C', '#FBE281', '#CB94F9', '#A5A5A5', '#262626', '#363B44', '#2452B2', '#3473A1', '#417A53', '#922B22', '#AD642A', '#9E8329', '#57297D', '#939393', '#0D0D0D', '#25272E', '#15316A', '#1C415A', '#284D34', '#511712', '#573213', '#635217', '#36194E'
    ],
    lineHeights: [
      { label: { en_US: 'Single', zh_CN: '单倍行距', ar_KSA: 'مفرد', ja_JP: 'シングル', ur_IN: 'ایک', hi_IN: 'सिंगल', kn_IN: 'ಪ್ರತಿ', ta_IN: 'தனி', te_IN: 'ఏక', sp_SPA: 'Sencillo' }, value: 1 },
      {
        label: { en_US: '1.5 Line Spacing', zh_CN: '1.5 倍行距', ar_KSA: 'تباعد الأسطر 1.5', ja_JP: '1.5倍行間', ur_IN: '1.5 لائن اسپیسنگ', hi_IN: '1.5 लाइन स्पेसिंग', kn_IN: '1.5 ಲೈನ್ ಸ್ಪೇಸಿಂಗ್', ta_IN: '1.5 வரி இடைவெளி', te_IN: '1.5 లైన్ స్పేసింగ్', sp_SPA: 'Espaciado de 1.5 líneas' },
        value: 1.5,
        default: true,
      },
      { label: { en_US: 'Double', zh_CN: '2 倍行距', ar_KSA: 'مزدوج', ja_JP: 'ダブル', ur_IN: 'ڈبل', hi_IN: 'डबल', kn_IN: 'ದ್ವಿಗುಣ', ta_IN: 'இரட்டி', te_IN: 'డబల్', sp_SPA: 'Doble' }, value: 2 },
      { label: { en_US: '2.5 Line Spacing', zh_CN: '2.5 倍行距', ar_KSA: 'تباعد الأسطر 2.5', ja_JP: '2.5倍行間', ur_IN: '2.5 لائن اسپیسنگ', hi_IN: '2.5 लाइन स्पेसिंग', kn_IN: '2.5 ಲೈನ್ ಸ್ಪೇಸಿಂಗ್', ta_IN: '2.5 வரி இடைவெளি', te_IN: '2.5 లైన్ స్పేసింగ్', sp_SPA: 'Espaciado de 2.5 líneas' }, value: 2.5 },
      { label: { en_US: 'Triple', zh_CN: '3 倍行距', ar_KSA: 'ثلاثي', ja_JP: 'トリプル', ur_IN: 'تریپل', hi_IN: 'त्रिपل', kn_IN: 'ಮೂರುಗುಣ', ta_IN: 'மூன்றிரட்டி', te_IN: 'మూడుగుణం', sp_SPA: 'Triple' }, value: 3 },
    ],
    symbols: [
      {
        label: { en_US: 'Plain Text', zh_CN: '普通文本', ar_KSA: 'نص عادي', ja_JP: 'プレーンテキスト', ur_IN: 'سادہ متن', hi_IN: 'सादा पाठ', kn_IN: 'ಸಾದಾ ಪರ್ಶ', ta_IN: 'சாதாரண உரை', te_IN: 'సాదా పాఠ్యం', sp_SPA: 'Texto Simple' },
        items: '‹›«»‘’“”‚„¡¿‥…‡‰‱‼⁈⁉⁇©®™§¶⁋',
      },
      {
        label: { en_US: 'Currency Symbols', zh_CN: '货币符号', ar_KSA: 'رموز العملة', ja_JP: '通貨記号', ur_IN: 'کرنسی کے نشان', hi_IN: 'मुद्रा चिह्न', kn_IN: 'ಕರೆನ್ಸಿ ಚಿನ್ಹೆಗಳು', ta_IN: 'பண குறிீடுகள்', te_IN: 'కరెన్సీ చిహ్నాలు', sp_SPA: 'Símbolos de Moneda' },
        items: '$€¥£¢₠₡₢₣₤¤₿₥₦₧₨₩₪₫₭₮₯₰₱₲₳₴₵₶₷₸₹₺₻₼₽',
      },
      {
        label: { en_US: 'Mathematical Symbols', zh_CN: '数学符号', ar_KSA: 'رموز رياضية', ja_JP: '数学記号', ur_IN: 'ریاضی کے نشان', hi_IN: 'गणित के चिह्न', kn_IN: 'ಗಣಿತ ಚಿನ್ಹೆಗಳು', ta_IN: 'கணித குறிீடுகள்', te_IN: 'గణిత చిహ్నాలు', sp_SPA: 'Símbolos Matemáticos' },
        items: '<>≤≥–—¯‾°−±÷⁄×ƒ∫∑∞√∼≅≈≠≡∈∉∋∏∧∨¬∩∪∂∀∃∅∇∗∝∠¼½¾',
      },
      { label: { en_US: 'Arrows', zh_CN: '箭头', ar_KSA: 'أسهم', ja_JP: '矢印', ur_IN: 'تیر', hi_IN: 'तीर', kn_IN: 'ಬಾಣಗಳು', ta_IN: 'அம்புகள்', te_IN: 'అమ్ములు', sp_SPA: 'Flechas' }, items: '←→↑↓⇐⇒⇑⇓⇠⇢⇡⇣⇤⇥⤒⤓↨' },
      {
        label: { en_US: 'Latin Script', zh_CN: '拉丁语', ar_KSA: 'الأبجدية اللاتينية', ja_JP: 'ラテン文字', ur_IN: 'لاطینی رسم الخط', hi_IN: 'लैटिन लिपि', kn_IN: 'ಲ್ಯಾಟಿನ್ ಲಿಪಿ', ta_IN: 'லத்தீன் எழுத்து', te_IN: 'లేటిన్ లిపి', sp_SPA: 'Escritura Latina' },
        items:
          'ĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁłŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽžſ',
      },
    ],
    emojis: [
      {
        label: { en_US: 'Emotions & People', zh_CN: '表情与角色', ar_KSA: 'مشاعر وأشخاص', ja_JP: '感情と人物', ur_IN: 'جذبات اور لوگ', hi_IN: 'भावनाएं और लोग', kn_IN: 'ಭಾವನೆಗಳು ಮತ್ತು ವ್ಯಕ್ತಿಗಳು', ta_IN: 'உணர்வுகள் மற்றும் மக்கள்', te_IN: 'భావనలు మరియు వ్యక్తులు', sp_SPA: 'Emociones y Personas' },
        items:
          '😀 😃 😄 😁 😆 😅 🤣 😂 🙂 🙃 🫠 😉 😊 😇 🥰 😍 🤩 😘 😗 ☺️ 😚 😙 🥲 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🫢 🫣 🤫 🤔 🫡 🤐 🤨 😐 😑 😶 🫥 😶‍🌫️ 😏 😒 🙄 😬 😮‍💨 🤥 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🤧 🥵 🥶 🥴 😵 😵‍💫 🤯 🤠 🥳 🥸 😎 🤓 🧐 😕 🫤 😟 🙁 ☹️ 😮 😯 😲 😳 🥺 🥹 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 ☠️ 💩 🤡 👹 👺 👻 👽 👾 🤖 👋 🤚 🖐️ ✋ 🖖 🫱 🫲 🫳 🫴 👌 🤌 🤏 ✌️ 🤞 🫰 🤟 🤘 🤙 👈 👉 👆 🖕 👇 ☝️ 🫵 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 🫶 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 🦿 🦵 🦶 👂 🦻',
      },
      {
        label: { en_US: 'Animals & Nature', zh_CN: '动物与自然', ar_KSA: 'حيوانات وطبيعة', ja_JP: '動物と自然', ur_IN: 'جانور اور قدرت', hi_IN: 'जानवर और प्रकृति', kn_IN: 'ಪ್ರಾಣಿಗಳು ಮತ್ತು ಪ್ರಕೃತಿ', ta_IN: 'விலங்குகள் மற்றும் இயற்கை', te_IN: 'జీవంతులు మరియు ప్రకృతి' },
        items:
          '🐵 🐒 🦍 🦧 🐶 🐕 🦮 🐕‍🦺 🐩 🐺 🦊 🦝 🐱 🐈 🐈‍⬛ 🦁 🐯 🐅 🐆 🐴 🐎 🦄 🦓 🦌 🦬 🐮 🐂 🐃 🐄 🐷 🐖 🐗 🐽 🐏 🐑 🐐 🐪 🐫 🦙 🦒 🐘 🦣 🦏 🦛 🐭 🐁 🐀 🐹 🐰 🐇 🐿️ 🦫 🦔 🦇 🐻 🐻‍❄️ 🐨 🐼 🦥 🦦 🦨 🦘 🦡 🐾 🦃 🐔 🐓 🐣 🐤 🐥 🐦 🐧 🕊️ 🦅 🦆 🦢 🦉 🦤 🪶 🦩 🦚 🦜 🐸 🐊 🐢 🦎 🐍 🐲 🐉 🦕 🦖 🐳 🐋 🐬 🦭 🐟 🐠 🐡 🦈 🐙 🐚 🪸 🐌 🦋 🐛 🐜 🐝 🪲 🐞 🦗 🪳 🕷️ 🕸️ 🦂 🦟 🪰 🪱 🦠 💐 🌸 💮 🪷 🏵️ 🌹 🥀 🌺 🌻 🌼 🌷 🌱 🪴 🌲 🌳 🌴 🌵 🌾 🌿 ☘️ 🍀 🍁 🍂 🍃 🪹 🪺',
      },
      {
        label: { en_US: 'Food & Drink', zh_CN: '食物与食品', ar_KSA: 'طعام وشراب', ja_JP: '食べ物と飲み物', ur_IN: 'کھانا اور پینا', hi_IN: 'खाना और पीना', kn_IN: 'ಆಹಾರ ಮತ್ತು ಪಾನೀಯ', ta_IN: 'உணவு மற்றும் பಾனీயம்', te_IN: 'ఆహారం మరియు పానీయం' },
        items:
          '🥬 🥦 🧄 🧅 🍄 🥜 🫘 🌰 🍞 🥐 🥖 🫓 🥨 🥯 🥞 🧇 🧀 🍖 🍗 🥩 🥓 🍔 🍟 🍕 🌭 🥪 🌮 🌯 🫔 🥙 🧆 🥚 🍳 🥘 🍲 🫕 🥣 🥗 🍿 🧈 🧂 🥫 🍱 🍘 🍙 🍚 🍛 🍜 🍝 🍠 🍢 🍣 🍤 🍥 🥮 🍡 🥟 🥠 🥡 🦀 🦞 🦐 🦑 🦪 🍦 🍧 🍨 🍩 🍪 🎂 🍰 🧁 🥧 🍫 🍬 🍭 🍮 🍯 🍼 🥛 ☕ 🫖 🍵 🍶 🍾 🍷 🍸 🍹 🍺 🍻 🥂 🥃 🫗 🥤 🧋 🧃 🧉 🧊 🥢 🍽️ 🍴 🥄 🔪 🫙 🏺',
      },
      {
        label: { en_US: 'Activities', zh_CN: '活动', ar_KSA: 'أنشطة', ja_JP: '活動', ur_IN: 'سرگرمیاں', hi_IN: 'गतिविधियाँ', kn_IN: 'ಚಾಲನೆಗಳು', ta_IN: 'செயல்பಾடுகள்', te_IN: 'క్రీడలు' },
        items:
          '🎗️ 🎟️ 🎫 🎖️ 🏆 🏅 🥇 🥈 🥉 ⚽ ⚾ 🥎 🏀 🏐 🏈 🏉 🎾 🥏 🎳 🏏 🏑 🏒 🥍 🏓 🏸 🥊 🥋 🥅 ⛳ ⛸️ 🎣 🤿 🎽 🎿 🛷 🥌 🎯 🪀 🪁 🎱 🔮 🪄 🧿 🪬 🎮 🕹️ 🎰 🎲 🧩 🧸 🪅 🪩 🪆 ♠️ ♥️ ♦️ ♣️ ♟️ 🃏 🀄 🎴 🎭 🖼️ 🎨 🧵 🪡 🧶 🪢',
      },
      {
        label: { en_US: 'Travel & Places', zh_CN: '旅行与景点', ar_KSA: 'سفر وأماكن', ja_JP: '旅行と場所', ur_IN: 'سفر اور جگہیں', hi_IN: 'यात्रा और स्थान', kn_IN: 'ಪ್ರವಾಸ ಮತ್ತು ಸ್ಥಳಗಳು', ta_IN: 'பயணம் மற்றும் இடங்கள்', te_IN: 'ప్రయాణం మరియు స్థలాలు' },
        items:
          '🚈 🚉 🚊 🚝 🚞 🚋 🚌 🚍 🚎 🚐 🚑 🚒 🚓 🚔 🚕 🚖 🚗 🚘 🚙 🛻 🚚 🚛 🚜 🏎️ 🏍️ 🛵 🦽 🦼 🛺 🚲 🛴 🛹 🛼 🚏 🛣️ 🛤️ 🛢️ ⛽ 🛞 🚨 🚥 🚦 🛑 🚧 ⚓ 🛟 ⛵ 🛶 🚤 🛳️ ⛴️ 🛥️ 🚢 ✈️ 🛩️ 🛫 🛬 🪂 💺 🚁 🚟 🚠 🚡 🛰️ 🚀 🛸 🛎️ 🧳 ⌛ ⏳ ⌚ ⏰ ⏱️ ⏲️ 🕰️ 🕛 🕧 🕐 🕜 🕑 🕝 🕒 🕞 🕓 🕟 🕔 🕠 🕕 🕡 🕖 🕢 🕗 🕣 🕘 🕤 🕙 🕥 🕚 🕦 🌑 🌒 🌓 🌔 🌕 🌖 🌗 🌘 🌙 🌚 🌛 🌜 🌡️ ☀️ 🌝 🌞 🪐 ⭐ 🌟 🌠 🌌 ☁️ ⛅ ⛈️ 🌤️ 🌥️ 🌦️ 🌧️ 🌨️ 🌩️ 🌪️ 🌫️ 🌬️ 🌀 🌈 🌂 ☂️ ☔ ⛱️ ⚡ ❄️ ☃️ ⛄ ☄️ 🔥 💧 🌊',
      },
      {
        label: { en_US: 'Objects', zh_CN: '物品', ar_KSA: 'أشياء', ja_JP: '物体', ur_IN: 'اشیاء', hi_IN: 'वस्तुएं', kn_IN: 'ವಸ್ತುಗಳು', ta_IN: 'பೊருட்கள்', te_IN: 'వస్తువులు' },
        items:
          '📃 📜 📄 📰 🗞️ 📑 🔖 🏷️ 💰 🪙 💴 💵 💶 💷 💸 💳 🧾 💹 ✉️ 📧 📨 📩 📤 📥 📦 📫 📪 📬 📭 📮 🗳️ ✏️ ✒️ 🖋️ 🖊️ 🖌️ 🖍️ 📝 💼 📁 📂 🗂️ 📅 📆 🗒️ 🗓️ 📇 📈 📉 📊 📋 📌 📍 📎 🖇️ 📏 📐 ✂️ 🗃️ 🗄️ 🗑️ 🔒 🔓 🔏 🔐 🔑 🗝️ 🔨 🪓 ⛏️ ⚒️ 🛠️ 🗡️ ⚔️ 🔫 🪃 🏹 🛡️ 🪚 🔧 🪛 🔩 ⚙️ 🗜️ ⚖️ 🦯 🔗 ⛓️ 🪝 🧰 🧲 🪜 ⚗️ 🧪 🧫 🧬 🔬 🔭 📡 💉 🩸 💊 🩹 🩼 🩺 🩻 🚪 🛗 🪞 🪟 🛏️ 🛋️ 🪑 🚽 🪠 🚿 🛁 🪤 🪒 🧴 🧷 🧹 🧺 🧻 🪣 🧼 🫧 🪥 🧽 🧯 🛒 🚬 ⚰️ 🪦 ⚱️ 🗿 🪧 🪪',
      },
      {
        label: { en_US: 'Symbols', zh_CN: '符号', ar_KSA: 'رموز', ja_JP: 'シンボル', ur_IN: 'علامت', hi_IN: 'प्रतीक', kn_IN: 'ಚಿನ್ಹೆಗಳು', ta_IN: 'குறிீடுகள்', te_IN: 'చిహ్నాలు' },
        items:
          '➰ ➿ 〽️ ✳️ ✴️ ❇️ ©️ ®️ ™️ #️⃣ *️⃣ 0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 🔠 🔡 🔢 🔣 🔤 🅰️ 🆎 🅱️ 🆑 🆒 🆓 ℹ️ 🆔 Ⓜ️ 🆕 🆖 🅾️ 🆗 🅿️ 🆘 🆙 🆚 🈁 🈂️ 🔴 🟠 🟡 🟢 🔵 🟣 🟤 ⚫ ⚪ 🟥 🟧 🟨 🟩 🟦 🟪 🟫 ⬛ ⬜ ◼️ ◻️ ◾ ◽ ▪️ ▫️ 🔶 🔷 🔸 🔹 🔺 🔻 💠 🔘 🔳 🔲',
      },
      {
        label: { en_US: 'Flags', zh_CN: '旗帜', ar_KSA: 'أعلام', ja_JP: '旗', ur_IN: 'جھنڈے', hi_IN: 'झंडे', kn_IN: 'ಧ್ವಜಗಳು', ta_IN: 'கೊடிகள்', te_IN: 'కొడిగులు' },
        items:
          '🏁 🇨🇳 🎌 🇩🇪 🇪🇸 🇦🇨 🇦🇩 🇦🇪 🇦🇫 🇦🇬 🇦🇮 🇦🇱 🇦🇲 🇦🇴 🇦🇶 🇦🇷 🇦🇸 🇦🇹 🇦🇺 🇦🇼 🇦🇽 🇦🇿 🇧🇦 🇧🇧 🇧🇩 🇧🇪 🇧🇫 🇧🇬 🇧🇭 🇧🇮 🇧🇯 🇧🇱 🇧🇲 🇧🇳 🇧🇴 🇧🇶 🇧🇷 🇧🇸 🇧🇹 🇧🇻 🇧🇼 🇧🇾 🇧🇿 🇨🇦 🇨🇨 🇨🇩 🇨🇫 🇨🇬 🇨🇭 🇨🇮 🇨🇰 🇨🇱 🇨🇲 🇨🇴 🇨🇵 🇨🇷 🇨🇺 🇨🇻 🇨🇼 🇨🇽 🇨🇾 🇨🇿 🇩🇬 🇩🇯 🇩🇰 🇩🇲 🇩🇴 🇩🇿 🇪🇦 🇪🇨 🇪🇪 🇪🇬 🇪🇭 🏴󠁧󠁢󠁥󠁮󠁧󠁿 🇪🇷 🇪🇹 🇪🇺 🇫🇮 🇫🇯 🇫🇰 🇫🇲 🇫🇴 🇬🇦 🇬🇩 🇬🇪 🇬🇫 🇬🇬 🇬🇭 🇬🇮 🇬🇱 🇬🇲 🇬🇳 🇬🇵 🇬🇶 🇬🇷 🇬🇸 🇬🇹 🇬🇺 🇬🇼 🇬🇾 🇭🇰 🇭🇲 🇭🇳 🇭🇷 🇭🇹 🇭🇺 🇮🇨 🇮🇩 🇮🇪 🇮🇱 🇮🇲 🇮🇳 🇮🇴 🇮🇶 🇮🇷 🇮🇸 🇯🇪 🇯🇲 🇯🇴 🇰🇪 🇰🇬 🇰🇭 🇰🇮 🇰🇲 🇰🇳 🇰🇵 🇰🇼 🇰🇾 🇰🇿 🇱🇦 🇱🇧 🇱🇨 🇱🇮 🇱🇰 🇱🇷 🇱🇸 🇱🇹 🇱🇺 🇱🇻 🇱🇾 🇲🇦 🇲🇨 🇲🇩 🇲🇪 🇲🇫 🇲🇬 🇲🇭 🇲🇰 🇲🇱 🇲🇲 🇲🇳 🇲🇴 🇲🇵 🇲🇶 🇲🇷 🇲🇸 🇲🇹 🇲🇺 🇲🇻 🇲🇼 🇲🇽 🇲🇾 🇲🇿 🇳🇦 🇳🇨 🇳🇪 🇳🇫 🇳🇬 🇳🇮 🇳🇱 🇳🇴',
      },
    ],
    pageSizes: [
      { label: 'A4', width: 21.0, height: 29.4, default: true },
      { label: 'A3', width: 29.7, height: 42.0 },
      { label: 'A5', width: 14.8, height: 21.0 },
      { label: 'B5', width: 17.6, height: 25.0 },
      {
        label: { en_US: 'No. 5 Envelope', zh_CN: '5号信封', ar_KSA: 'ظرف رقم ٥ ', ja_JP: '5号封筒 ', ur_IN: 'نمبر ۵ کا لفافہ', hi_IN: 'नंबर 5 लिफ़ाफ़ा', kn_IN: 'ನಂ. 5 ಲಕೋಟೆ', ta_IN: 'எண் 5 உறை', te_IN: 'నెం. 5 కవరు' },
        width: 10.9,
        height: 12.9,
      },
      {
        label: { en_US: 'No. 6 Envelope', zh_CN: '6号信封', ar_KSA: 'ظرف رقم ٦ ', ja_JP: '6号封筒 ', ur_IN: 'نمبر ۶ کا لفافہ', hi_IN: 'नंबर 6 लिफ़ाफ़ा', kn_IN: 'ನಂ. 6 ಲಕೋಟೆ', ta_IN: 'எண் 6 உறை', te_IN: 'నెం. 6 కవరు' },
        width: 11.9,
        height: 22.9,
      },
      {
        label: { en_US: 'No. 7 Envelope', zh_CN: '7号信封', ar_KSA: 'ظرف رقم ٧ ', ja_JP: '7号封筒 ', ur_IN: 'نمبر ۷ کا لفافہ', hi_IN: 'नंबर 7 लिफ़ाफ़ा', kn_IN: 'ನಂ. 7 ಲಕೋಟೆ', ta_IN: 'எண் 7 உறை', te_IN: 'నెం. 7 కవరు' },
        width: 16.1,
        height: 22.8,
      },
      {
        label: { en_US: 'No. 9 Envelope', zh_CN: '9号信封', ar_KSA: 'ظرف رقم ٩ ', ja_JP: '9号封筒 ', ur_IN: 'نمبر ۹ کا لفافہ', hi_IN: 'नंबर 9 लिफ़ाफ़ा', kn_IN: 'ನಂ. 9 ಲಕೋಟೆ', ta_IN: 'எண் 9 உறை', te_IN: 'నెం. 9 కవరు' },
        width: 22.8,
        height: 32.3,
      },
      {
        label: { en_US: 'Legal Paper', zh_CN: '法律用纸', ar_KSA: 'ورق قانوني', ja_JP: 'リーガル用紙', ur_IN: 'قانونی کاغذ', hi_IN: 'कानूनी कागज़', kn_IN: 'ಕಾನೂನು ಕಾಗದ', ta_IN: 'சட்ட காகிதம்', te_IN: 'చట్టపరమైన కాగితం' },
        width: 21.5,
        height: 33.5,
      },
      {
        label: { en_US: 'Letter Paper', zh_CN: '信纸', ar_KSA: 'ورق الرسائل', ja_JP: 'レター用紙', ur_IN: 'خط کا کاغذ', hi_IN: 'पत्र कागज़', kn_IN: 'ಪತ್ರ ಕಾಗದ', ta_IN: 'கடித காகிதம்', te_IN: 'లేఖ కాగితం' },
        width: 21.5,
        height: 27.9,
      },
    ],
  },
  toolbar: {
    defaultMode: 'ribbon',
    enableSourceEditor: false,
    menus: ['base', 'insert', 'table', 'tools', 'page', 'export', 'latex'],
    disableMenuItems: [],
    importWord: {
      enabled: true,
      options: {},
      useCustomMethod: false,
    },
  },
  page: {
    defaultMargin: {
      left: 3.18,
      right: 3.18,
      top: 2.54,
      bottom: 2.54,
    },
    defaultOrientation: 'portrait',
    defaultBackground: '#fff',
    watermark: {
      type: 'compact',
      alpha: 0.2,
      fontColor: '#000',
      fontSize: 16,
      fontFamily: 'SimSun',
      fontWeight: 'normal',
      text: '',
    },
    /*
     *新添加的 bolck 自定义节点 需要参与的情况这里需要  types添加对应的类型types: ["myBlock"],
     * 如果是是用nodeView 实现的节点需要  自定义节点外层添加代码  :id="node.attrs.id" 参考image
     * 如果需要添加自定义计算方法 需要在  nodesComputedOption 添加计算方法
     * 列如: 新添加节点名字为 'myBlock'
     * 添加计算方法
     *  nodesComputedOption:{
     *   types: ["myBlock"],
     *   nodesComputed: {
     *   'myBlock':(splitContex, node, pos, parent, dom)=>{
     *    //计算代码
     *   }
     * }
     *
     * } 否则走默认的计算
     * */
    nodesComputedOption: {
      types: [],
      nodesComputed: {},
    },
  },
  document: {
    title: '',
    content: '',
    placeholder: {
      en_US: 'Please enter the document content...',
      zh_CN: '请输入文档内容...',
      ar_KSA: 'الرجاء إدخال محتوى الوثيقة...',
      ja_JP: 'ドキュメントの内容を入力してください...',
      ur_IN: 'براہ کرم دستاویز کا مواد درج کریں...',
      hi_IN: 'कृपया दस्तावेज़ की सामग्री दर्ज करें...',
      kn_IN: 'ದಯವಿಟ್ಟು ಡಾಕ್ಯುಮೆಂಟ್ ವಿಷಯವನ್ನು ನಮೂದಿಸಿ...',
      ta_IN: 'ஆவணத்தின் உள்ளடக்கத்தை உள்ளிடவும்...',
      te_IN: 'దయచేసి పత్రం కంటెంట్‌ను నమోదు చేయండి...',
      sp_SPA: 'Por favor, ingrese el contenido del documento...',
    },
    enableSpellcheck: true,
    enableMarkdown: true,
    enableBubbleMenu: true,
    enableBlockMenu: true,
    readOnly: false,
    autofocus: true,
    characterLimit: 0,
    typographyRules: {},
    // https://prosemirror.net/docs/ref/#view.EditorProps
    editorProps: {},
    // https://prosemirror.net/docs/ref/#model.ParseOptions
    parseOptions: {
      preserveWhitespace: 'full',
    },
    autoSave: {
      enabled: true,
      interval: 300000,
    },
  },
  assistant: {
    enabled: false,
    maxlength: 100,
    commands: [
      {
        label: { en_US: 'Continuation', zh_CN: '续写', ar_KSA: 'عربي', ja_JP: '日本語', ur_IN: 'اردو', hi_IN: 'हिंदी', kn_IN: 'ಕನ್ನಡ', ta_IN: 'தமிழ்', te_IN: 'తెలుగు' },
        value: { en_US: 'Continuation', zh_CN: '续写', ar_KSA: 'عربي', ja_JP: '日本語', ur_IN: 'اردو', hi_IN: 'हिंदी', kn_IN: 'ಕನ್ನಡ', ta_IN: 'தமிழ்', te_IN: 'తెలుగు' },
      },
      {
        label: { en_US: 'Rewrite', zh_CN: '重写', ar_KSA: 'إعادة كتابة', ja_JP: '書き直し', ur_IN: 'دوبارہ لکھیں', hi_IN: 'फिर से लिखें', kn_IN: 'ಮರುಬರೆಯಿರಿ', ta_IN: 'மீண்டும் எழுதுங்கள்', te_IN: 'మళ్లీ వ్రాయండి' },
        value: { en_US: 'Rewrite', zh_CN: '重写', ar_KSA: 'إعادة كتابة', ja_JP: '書き直し', ur_IN: 'دوبارہ لکھیں', hi_IN: 'फिर से लिखें', kn_IN: 'ಮರುಬರೆಯಿರಿ', ta_IN: 'மீண்டும் எழுதுங்கள்', te_IN: 'మళ్లీ వ్రాయండి' },
      },
      {
        label: { en_US: 'Abbreviation', zh_CN: '缩写', ar_KSA: 'اختصار', ja_JP: '省略', ur_IN: 'مختصر', hi_IN: 'संक्षेप', kn_IN: 'ಸಂಕ್ಷೇಪ', ta_IN: 'சுருக்கம்', te_IN: 'సంక్షేపణ' },
        value: { en_US: 'Abbreviation', zh_CN: '缩写', ar_KSA: 'اختصار', ja_JP: '省略', ur_IN: 'مختصر', hi_IN: 'संक्षेप', kn_IN: 'ಸಂಕ್ಷೇಪ', ta_IN: 'சுருக்கம்', te_IN: 'సంక్షేపణ' },
      },
      {
        label: { en_US: 'Expansion', zh_CN: '扩写', ar_KSA: 'توسيع', ja_JP: '拡張', ur_IN: 'توسیع', hi_IN: 'विस्तार', kn_IN: 'ವಿಸ್ತರಣೆ', ta_IN: 'விரிவாக்கம்', te_IN: 'విస్తరణ' },
        value: { en_US: 'Expansion', zh_CN: '扩写', ar_KSA: 'توسيع', ja_JP: '拡張', ur_IN: 'توسیع', hi_IN: 'विस्तार', kn_IN: 'ವಿಸ್ತರಣೆ', ta_IN: 'விரிவாக்கம்', te_IN: 'విస్తరణ' },
      },
      {
        label: { en_US: 'Polish', zh_CN: '润色', ar_KSA: 'تلميع', ja_JP: '磨き上げ', ur_IN: 'چمکانا', hi_IN: 'चमकाना', kn_IN: 'ಹೊಳಪು ಮಾಡಿ', ta_IN: 'மெருகேற்றுங்கள்', te_IN: 'మెరుగుపరచండి' },
        value: { en_US: 'Polish', zh_CN: '润色', ar_KSA: 'تلميع', ja_JP: '磨き上げ', ur_IN: 'چمکانا', hi_IN: 'चमकाना', kn_IN: 'ಹೊಳಪು ಮಾಡಿ', ta_IN: 'மெருகேற்றுங்கள்', te_IN: 'మెరుగుపరచండి' },
      },
      {
        label: { en_US: 'Proofread', zh_CN: '校阅', ar_KSA: 'تدقيق', ja_JP: '校正', ur_IN: 'پروف ریڈنگ', hi_IN: 'प्रूफरीडिंग', kn_IN: 'ಪ್ರೂಫ್‌ರೀಡಿಂಗ್', ta_IN: 'ஆய்வு செய்யுங்கள்', te_IN: 'దిద్దుబాటు చేయండి' },
        value: { en_US: 'Proofread', zh_CN: '校阅', ar_KSA: 'تدقيق', ja_JP: '校正', ur_IN: 'پروف ریڈنگ', hi_IN: 'प्रूफरीडिंग', kn_IN: 'ಪ್ರೂಫ್‌ರೀಡಿಂಗ್', ta_IN: 'ஆய்வு செய்யுங்கள்', te_IN: 'దిద్దుబాటు చేయండి' },
      },
      {
        label: { en_US: 'Translate', zh_CN: '翻译', ar_KSA: 'ترجمة', ja_JP: '翻訳', ur_IN: 'ترجمہ', hi_IN: 'अनुवाद', kn_IN: 'ಅನುವಾದ', ta_IN: 'மொழிபெயர்ப்பு', te_IN: 'అనువాదం' },
        value: { en_US: 'Translate to chinese', zh_CN: '翻译成英文', ar_KSA: 'ترجمة إلى الصينية', ja_JP: '中国語に翻訳', ur_IN: 'چینی میں ترجمہ کریں', hi_IN: 'चीनी में अनुवाद करें', kn_IN: 'ಚೈನೀಸ್‌ಗೆ ಅನುವಾದಿಸಿ', ta_IN: 'சீன மொழிக்கு மொழிபெயர்க்கவும்', te_IN: 'చైనీస్‌లోకి అనువదించండి' },
        autoSend: false,
      },
    ],
  },
  templates: [],
  cdnUrl: 'https://unpkg.com/@umoteam/editor-external@latest',
  shareUrl: location?.href || '',
  diagrams: {
    domain: 'https://embed.diagrams.net',
    // https://www.drawio.com/doc/faq/supported-url-parameters
    params: {},
  },
  file: {
    allowedMimeTypes: [],
    maxSize: 1024 * 1024 * 100, // 100M
  },
  extensions: [],
  translations: {
    en_US: {},
    zh_CN: {},
    ar_KSA: {},
    ja_JP: {},
    ur_IN: {},
    hi_IN: {},
    kn_IN: {},
    ta_IN: {},
    te_IN: {},
    sp_SPA: {},
  },
  async onSave(content, page, document) {
    throw new Error('Key "onSave": Please set the save method')
  },
  async onFileUpload(file) {
    if (!file) {
      throw new Error('File not found')
    }
    throw new Error('Key "onFileUpload": Please set the upload method')
  },
  onFileDelete(id, src) {
    console.error(
      'The file has been deleted. Please configure the onFileDelete to completely delete the file from the server.',
    )
  },
  async onAssistant(payload, content) {
    throw new Error('Key "onAssistant": Please set the onAssistant method')
  },
  async onCustomImportWordMethod(file) {
    throw new Error(
      'Key "onCustomImportWordMethod": Please set the onAssistant method',
    )
  },
}

// 组件 props 所需格式
const propsOptions = Object.keys(defaultOptions)

const isNumber = (value) => {
  if (typeof value === 'number') {
    return isFinite(value)
  }
  if (typeof value === 'string') {
    const parsed = parseFloat(value)
    return !isNaN(parsed) && isFinite(parsed) && value === parsed.toString()
  }
  return false
}
const isLocale = (value) => {
  if (typeof value === 'string' && value.length > 0) {
    return true
  }
  if (typeof value === 'object' && value !== null) {
    for (let key in value) {
      if (!['en_US', 'zh_CN', 'ar_KSA', 'ja_JP', 'ur_IN', 'hi_IN', 'kn_IN', 'ta_IN', 'te_IN', 'sp_SPA'].includes(key)) {
        return false
      }
    }
    return true
  }
  return false
}
const isAsyncFunction = (value) => {
  return (
    value.constructor.name === 'AsyncFunction' ||
    Promise.resolve(value) instanceof Promise
  )
}

const ojbectSchema = new ObjectSchema({
  editorKey: {
    merge: 'replace',
    validate: 'string!',
  },
  locale: {
    merge: 'replace',
    validate(value) {
      if (value && !['en-US', 'zh-CN', 'ar-KSA', 'ja-JP', 'ur-IN', 'hi-IN', 'kn-IN', 'ta-IN', 'te-IN', 'sp-SPA'].includes(value)) {
        throw new Error('Key "locale": must be one of "en-US", "zh-CN", "ar-KSA", "ja-JP", "ur-IN", "hi-IN", "kn-IN", "ta-IN", "te-IN", or "sp-SPA".')
      }
    },
  },
  theme: {
    merge: 'replace',
    validate(value) {
      if (value && !['dark', 'light', 'auto'].includes(value)) {
        throw new Error(
          'Key "theme": must be one of "dark", "light" or "auto".',
        )
      }
    },
  },
  height: {
    merge: 'replace',
    validate: 'string!',
  },
  dicts: {
    schema: {
      fonts: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "dicts": Key "fonts" must be a array.')
          }
          value.forEach((item) => {
            if (!item.label || (!item.value && item.value !== null)) {
              throw new Error(
                'Key "dicts": Key "fonts" must be a array of objects with "label" and "value" properties.',
              )
            }
          })
        },
      },
      colors: {
        merge: 'replace',
        validate: 'array',
      },
      lineHeights: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "dicts": Key "lineHeights": must be a array.')
          }
          if (!value.find((item) => item.default)) {
            throw new Error(
              'Key "dicts": Key "lineHeights": please set a default value.',
            )
          }
          value.forEach((item, index) => {
            if (!item.label || (!item.value && item.value !== null)) {
              throw new Error(
                `Key "dicts": Key "lineHeights[${index}]": must be a array of objects with "label" and "value" properties.`,
              )
            }
            if (!isLocale(item.label)) {
              throw new Error(
                `Key "dicts": Key "lineHeights[${index}]": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
          })
        },
      },
      symbols: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "dicts": Key "symbols" must be a array.')
          }
          value.forEach((item, index) => {
            if (!item.label || typeof item.items !== 'string') {
              throw new Error(
                `Key "dicts": Key "symbols[${index}]": must be a array of objects with "label" and "items" properties.`,
              )
            }
            if (!isLocale(item.label)) {
              throw new Error(
                `Key "dicts": Key "symbols[${index}]": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
          })
        },
      },
      emojis: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "dicts": Key "emojis" must be a array.')
          }
          value.forEach((item, index) => {
            if (!item.label || typeof item.items !== 'string') {
              throw new Error(
                `Key "dicts": Key "emojis[${index}]": must be a array of objects with "label" and "value" properties.`,
              )
            }
            if (!isLocale(item.label)) {
              throw new Error(
                `Key "dicts": Key "emojis[${index}]": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
          })
        },
      },
      pageSizes: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "dicts": Key "pageSizes": must be a array.')
          }
          if (!value.find((item) => item.default)) {
            throw new Error(
              'Key "dicts": Key "pageSizes": please set a default value.',
            )
          }
          value.forEach((item, index) => {
            if (!item.label || item.label === '') {
              throw new Error(
                `Key "dicts": Key "pageSizes[${index}]" Key: "label" cannot be empty.`,
              )
            }
            if (!isLocale(item.label)) {
              throw new Error(
                `Key "dicts": Key "pageSizes[${index}]": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
            if (!isNumber(item.width)) {
              throw new Error(
                `Key "dicts": Key "pageSizes[${index}]" Key: "width" must be a number.`,
              )
            }
            if (!isNumber(item.height)) {
              throw new Error(
                `Key "dicts": Key "pageSizes[${index}]" Key: "height" must be a number.`,
              )
            }
          })
        },
      },
    },
  },
  toolbar: {
    schema: {
      defaultMode: {
        merge: 'replace',
        validate(value) {
          if (value && !['classic', 'ribbon'].includes(value)) {
            throw new Error(
              'Key "toolbar": Key "defaultMode" must be one of "classic" or "ribbon".',
            )
          }
        },
      },
      enableSourceEditor: {
        merge: 'replace',
        validate: 'boolean',
      },
      menus: {
        merge: 'replace',
        validate(value) {
          const defaultMenus = ['base', 'insert', 'table', 'tools', 'page', 'export', 'latex']
          if (value && !Array.isArray(value)) {
            throw new Error('Key "toolbar": Key "menus" must be a array.')
          }
          if (!value.includes('base')) {
            throw new Error(
              'Key "toolbar": Key "menus" should at least contain "base".',
            )
          }
          if (!value.every((item) => defaultMenus.includes(item))) {
            throw new Error(
              `Key "toolbar": Key "menus" the array items of toolbar.menus must contain only one or multiple of ${JSON.stringify(defaultMenus)}.`,
            )
          }
        },
      },
      disableMenuItems: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error(
              'Key "toolbar": Key "disableMenuItems" must be a array.',
            )
          }
        },
      },
      importWord: {
        merge: 'replace',
        validate: 'object',
      },
    },
  },
  page: {
    schema: {
      defaultMargin: {
        schema: {
          left: {
            merge: 'replace',
            validate: 'number',
          },
          right: {
            merge: 'replace',
            validate: 'number',
          },
          top: {
            merge: 'replace',
            validate: 'number',
          },
          bottom: {
            merge: 'replace',
            validate: 'number',
          },
        },
      },
      defaultOrientation: {
        merge: 'replace',
        validate(value) {
          if (value && !['portrait', 'landscape'].includes(value)) {
            throw new Error(
              'Key "page": Key "defaultOrientation" must be one of "portrait" or "landscape".',
            )
          }
        },
      },
      defaultBackground: {
        merge: 'replace',
        validate: 'string',
      },
      watermark: {
        schema: {
          type: {
            merge: 'replace',
            validate(value) {
              if (value && !['compact', 'spacious'].includes(value)) {
                throw new Error(
                  'Key "watermark": Key "type" must be one of "compact" or "spacious".',
                )
              }
            },
          },
          alpha: {
            merge: 'replace',
            validate: 'number',
          },
          fontColor: {
            merge: 'replace',
            validate: 'string',
          },
          fontFamily: {
            merge: 'replace',
            validate(value) {
              if (value !== null && typeof value !== 'string') {
                throw new Error(
                  'Key "watermark": Key "fontFamily" must be a string.',
                )
              }
            },
          },
          fontSize: {
            merge: 'replace',
            validate: 'number',
          },
          fontWeight: {
            merge: 'replace',
            validate: 'string',
          },
          text: {
            merge: 'replace',
            validate: 'string',
          },
        },
      },
      nodesComputedOption: {
        schema: {
          types: {
            merge: 'replace',
            validate(value) {},
          },
          nodesComputed: {
            merge: 'replace',
            validate(value) {},
          },
        },
      },
    },
  },
  document: {
    schema: {
      title: {
        merge: 'replace',
        validate: 'string',
      },
      content: {
        merge: 'replace',
        validate() {},
      },
      placeholder: {
        merge: 'replace',
        validate(value) {
          if (!isLocale(value)) {
            throw new Error(
              `Key "document": Key "title": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
            )
          }
        },
      },
      enableSpellcheck: {
        merge: 'replace',
        validate: 'boolean',
      },
      enableMarkdown: {
        merge: 'replace',
        validate: 'boolean',
      },
      enableBubbleMenu: {
        merge: 'replace',
        validate: 'boolean',
      },
      enableBlockMenu: {
        merge: 'replace',
        validate: 'boolean',
      },
      readOnly: {
        merge: 'replace',
        validate: 'boolean',
      },
      autofocus: {
        merge: 'replace',
        validate(value) {
          if (
            !['start', 'end', 'all', true, false, null].includes(value) &&
            !isNumber(value)
          ) {
            throw new Error(
              'Key "document": Key "autofocus" must be one of "start", "end", "all", Number, true, false, null.',
            )
          }
        },
      },
      characterLimit: {
        merge: 'replace',
        validate: 'number',
      },
      typographyRules: {
        merge: 'replace',
        validate: 'object',
      },
      editorProps: {
        merge: 'replace',
        validate: 'object',
      },
      parseOptions: {
        merge: 'replace',
        validate: 'object',
      },
      autoSave: {
        schema: {
          enabled: {
            merge: 'replace',
            validate: 'boolean',
          },
          interval: {
            merge: 'replace',
            validate: 'number',
          },
        },
      },
    },
  },
  assistant: {
    schema: {
      enabled: {
        merge: 'replace',
        validate: 'boolean',
      },
      maxlength: {
        merge: 'replace',
        validate(value) {
          if (!isNumber(value) || !Number.isInteger(value) || value <= 0) {
            throw new Error(
              'Key "assistant": Key "maxlength" must be a number.',
            )
          }
        },
      },
      commands: {
        merge: 'replace',
        validate(value) {
          if (value && !Array.isArray(value)) {
            throw new Error('Key "assistant": Key "commands" must be a array.')
          }
          value.forEach((item) => {
            if (!item.label || !item.value) {
              throw new Error(
                'Key "assistant": Key "commands" must be a array of objects with "label" and "value" properties.',
              )
            }
            if (!isLocale(item.label)) {
              throw new Error(
                `Key "assistant": Key "commands[${index}]": Key "label" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
            if (!isLocale(item.value)) {
              throw new Error(
                `Key "assistant": Key "commands[${index}]": Key "value" must be string, or a object with "en_US" and "zh_CN" properties.`,
              )
            }
          })
        },
      },
    },
  },
  shareUrl: { merge: 'replace', validate: 'string' },
  templates: {
    merge: 'replace',
    validate(value) {
      if (value && !Array.isArray(value)) {
        throw new Error('Key "templates": Key "menus" must be a array.')
      }
      value.forEach((item, index) => {
        if (!item.title || !item.title === '') {
          throw new Error(
            `Key "templates[${index}]": Key "title" cannot be empty.`,
          )
        }
        if (!item.content || !item.content === '') {
          throw new Error(
            `Key "templates[${index}]": Key "content" cannot be empty.`,
          )
        }
      })
    },
  },
  cdnUrl: {
    merge: 'replace',
    validate: 'string',
  },
  diagrams: {
    merge: 'assign',
    validate: 'object',
  },
  file: {
    schema: {
      allowedMimeTypes: {
        merge: 'replace',
        validate: 'array',
      },
      maxSize: {
        merge: 'replace',
        validate: 'number',
      },
    },
  },
  extensions: {
    merge: 'replace',
    validate: 'array',
  },
  translations: {
    merge: 'replace',
    validate: 'object',
  },
  onSave: {
    merge: 'replace',
    validate(value) {
      if (!isAsyncFunction(value)) {
        throw new Error('Key "onSave" must be a async function.')
      }
    },
  },
  onFileUpload: {
    merge: 'replace',
    validate(value) {
      if (!isAsyncFunction(value)) {
        throw new Error('Key "onFileUpload" must be a async function.')
      }
    },
  },
  onFileDelete: {
    merge: 'replace',
    validate(value) {
      if (
        typeof value !== 'function' &&
        value.constructor.name !== 'AsyncFunction'
      ) {
        throw new Error('Key "onFileDelete" must be a function.')
      }
    },
  },
  onAssistant: {
    merge: 'replace',
    validate(value) {
      if (!isAsyncFunction(value)) {
        throw new Error('Key "onAssistant" must be a async function.')
      }
    },
  },
  onCustomImportWordMethod: {
    merge: 'replace',
    validate(value) {
      if (!isAsyncFunction(value)) {
        throw new Error(
          'Key "onCustomImportWordMethod" must be a async function.',
        )
      }
    },
  },
})

export { defaultOptions, propsOptions, ojbectSchema }
