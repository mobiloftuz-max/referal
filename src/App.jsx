import React, { useState, useEffect } from 'react';
import { 
  User, Coins, Gift, Users, Trophy, Settings, BookOpen, Lock, Unlock,
  RefreshCw, BarChart2, ShieldAlert, CheckCircle, XCircle, 
  Copy, PlusCircle, Trash, ExternalLink, ArrowRight, Eye, ShieldCheck, Ban, Sparkles
} from 'lucide-react';
import { supabase } from './supabase_client';

const maskText = (text) => {
  if (!text) return "";
  text = text.trim();
  if (!text) return "";
  return text.split(' ').map(part => {
    const len = part.length;
    if (len <= 2) {
      return len > 0 ? part[0] + "*" : "";
    } else if (len === 3) {
      return part[0] + "*" + part[2];
    } else if (len === 4) {
      return part[0] + "**" + part[3];
    } else {
      return part.slice(0, 2) + "***" + part[part.length - 1];
    }
  }).join(' ');
};

export default function App() {
  // Telegram WebApp API Integration
  const [tgUser, setTgUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [userData, setUserData] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [activeChannels, setActiveChannels] = useState([]);
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState({});
  const [usersList, setUsersList] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  
  // App navigation state: 'home' | 'course' | 'leaderboard' | 'admin'
  const [activeTab, setActiveTab] = useState('home');
  
  // Custom mock ID for development/testing in standard browsers
  const [mockId, setMockId] = useState('');
  const [isMockMode, setIsMockMode] = useState(false);
  
  // Inputs
  const [adminChannelId, setAdminChannelId] = useState('');
  const [adminChannelTitle, setAdminChannelTitle] = useState('');
  const [adminChannelLink, setAdminChannelLink] = useState('');
  
  // Settings Inputs
  const [thresholdInput, setThresholdInput] = useState('');
  const [courseLinkInput, setCourseLinkInput] = useState('');
  const [pointsPerReferralInput, setPointsPerReferralInput] = useState('');
  const [privateChannelIdInput, setPrivateChannelIdInput] = useState('');
  const [sharingTextInput, setSharingTextInput] = useState('');
  
  // UI states
  const [feedbackMsg, setFeedbackMsg] = useState({ text: '', type: '' });
  const [perfClass, setPerfClass] = useState('high'); // low | average | high
  const [showDebug, setShowDebug] = useState(false);

  // Admin IDs list
  const adminIds = (import.meta.env.VITE_ADMIN_IDS || '8544023815,8711912093')
    .split(',')
    .map(id => parseInt(id.trim(), 10));

  useEffect(() => {
    // 1. Hardware/Performance detection to maintain 60 FPS
    const cores = navigator.hardwareConcurrency || 4;
    if (cores <= 2) {
      setPerfClass('low');
    } else if (cores <= 4) {
      setPerfClass('average');
    } else {
      setPerfClass('high');
    }

    // Check debug mode
    if (window.location.search.includes('debug=true')) {
      setShowDebug(true);
    }

    // 2. Telegram WebApp initialization
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.initDataUnsafe?.user) {
        setTgUser(tg.initDataUnsafe.user);
        loadUser(tg.initDataUnsafe.user.id, tg.initDataUnsafe.user);
      } else {
        setIsMockMode(true);
        const defaultMock = 999999999;
        setTgUser({ id: defaultMock, first_name: 'Mock User', username: 'mock_user' });
        loadUser(defaultMock, { first_name: 'Mock User', username: 'mock_user' });
      }
    } else {
      setIsMockMode(true);
      const defaultMock = 999999999;
      setTgUser({ id: defaultMock, first_name: 'Mock User', username: 'mock_user' });
      loadUser(defaultMock, { first_name: 'Mock User', username: 'mock_user' });
    }
    
    loadLeaderboard();
    loadSettings();
  }, []);

  // Trigger Telegram Haptic Vibration
  const triggerHaptic = (type = 'light') => {
    const tg = window.Telegram?.WebApp;
    if (tg?.HapticFeedback) {
      if (type === 'success') {
        tg.HapticFeedback.notificationOccurred('success');
      } else if (type === 'error') {
        tg.HapticFeedback.notificationOccurred('error');
      } else {
        tg.HapticFeedback.impactOccurred('light');
      }
    }
  };

  // Load User Data from Supabase
  const loadUser = async (userId, tgProfile = null) => {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('users')
        .select('*')
        .eq('telegram_id', userId)
        .single();
        
      if (error) {
        if (error.code === 'PGRST116') {
          // User not found, create new unverified profile
          const newUser = {
            telegram_id: userId,
            username: tgProfile?.username || '',
            first_name: tgProfile?.first_name || 'Ishtirokchi',
            points: 0,
            referral_count: 0,
            is_banned: false,
            is_verified: false,
            created_at: new Date().toISOString()
          };
          
          const { data: created, error: insertErr } = await supabase
            .from('users')
            .insert([newUser])
            .select()
            .single();
          
          if (!insertErr && created) {
            setUserData(created);
          } else {
            setUserData(newUser);
          }
        } else {
          showFeedback('Xatolik yuz berdi: ' + error.message, 'error');
        }
      } else {
        setUserData(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Switch mock user for debugging
  const handleMockSwitch = () => {
    if (!mockId) return;
    const numId = parseInt(mockId, 10);
    const mockProfile = {
      id: numId,
      first_name: numId === 8544023815 ? 'Bosh Admin' : `Foydalanuvchi #${numId}`,
      username: numId === 8544023815 ? 'admin_boss' : `user_${numId}`
    };
    setTgUser(mockProfile);
    loadUser(numId, mockProfile);
    showFeedback(`Muvaffaqiyatli o'tildi: ${mockProfile.first_name}`, 'success');
  };

  // Load Leaderboard
  const loadLeaderboard = async () => {
    const { data, error } = await supabase
      .from('users')
      .select('first_name, username, referral_count, points')
      .eq('is_banned', false)
      .order('referral_count', { ascending: false })
      .limit(10);
      
    if (!error && data) {
      setLeaderboard(data);
    }
  };

  // Load Settings
  const loadSettings = async () => {
    const { data, error } = await supabase
      .from('settings')
      .select('*');
      
    if (!error && data) {
      const mapped = {};
      data.forEach(item => {
        mapped[item.key] = item.value;
      });
      setSettings(mapped);
      setThresholdInput(mapped.referral_threshold || '5');
      setCourseLinkInput(mapped.private_channel_link || '');
      setPointsPerReferralInput(mapped.points_per_referral || '1');
      setPrivateChannelIdInput(mapped.private_channel_id || '-1002000000000');
      setSharingTextInput(mapped.sharing_text || "🔥 Zuhra Olimova • Har bir qiz o‘z multfilmini yarata oladi!\n\nBot orqali ro'yxatdan o'ting va yopiq darslarga bepul kiring. Men ham boshladim, sizga ham tavsiya qilaman! 👇");
    }
  };

  // Load Admin Data (Channels, General Stats, Users List)
  const loadAdminData = async () => {
    if (!isAdmin()) return;
    
    // Load channels
    const { data: chs } = await supabase
      .from('channels')
      .select('*');
    if (chs) setActiveChannels(chs);
    
    // Load users list
    const { data: ulist } = await supabase
      .from('users')
      .select('*')
      .order('created_at', { ascending: false });
    if (ulist) setUsersList(ulist);
    
    // Calculate statistics
    if (ulist) {
      const total = ulist.length;
      const verified = ulist.filter(u => u.is_verified).length;
      const banned = ulist.filter(u => u.is_banned).length;
      
      const threshold = parseInt(settings.referral_threshold || '5', 10);
      const unlocked = ulist.filter(u => Math.max(u.referral_count || 0, u.points || 0) >= threshold).length;
      
      setStats({
        total_users: total,
        verified_users: verified,
        banned_users: banned,
        course_unlocked_users: unlocked
      });
    }
  };

  // Admin Actions: Add Channel
  const handleAdminAddChannel = async () => {
    if (!adminChannelId || !adminChannelTitle || !adminChannelLink) {
      showFeedback('Barcha maydonlarni to\'ldiring!', 'error');
      return;
    }
    
    const { error } = await supabase
      .from('channels')
      .insert([
        {
          tg_id: parseInt(adminChannelId, 10),
          title: adminChannelTitle.trim(),
          invite_link: adminChannelLink.trim(),
          creates_join_request: true
        }
      ]);
      
    if (!error) {
      showFeedback('Kanal muvaffaqiyatli qo\'shildi!', 'success');
      setAdminChannelId('');
      setAdminChannelTitle('');
      setAdminChannelLink('');
      loadAdminData();
    } else {
      showFeedback('Kanal qo\'shishda xatolik: ' + error.message, 'error');
    }
  };

  // Admin Actions: Delete Channel
  const handleAdminDelChannel = async (id) => {
    const { error } = await supabase
      .from('channels')
      .delete()
      .eq('id', id);
      
    if (!error) {
      showFeedback('Kanal ro\'yxatdan o\'chirildi!', 'success');
      loadAdminData();
    } else {
      showFeedback('O\'chirishda xatolik: ' + error.message, 'error');
    }
  };

  // Admin Actions: Save Global Settings
  const handleSaveSettings = async () => {
    try {
      const thresholdErr = await supabase
        .from('settings')
        .upsert({ key: 'referral_threshold', value: thresholdInput.trim() });
        
      const linkErr = await supabase
        .from('settings')
        .upsert({ key: 'private_channel_link', value: courseLinkInput.trim() });

      const pointsErr = await supabase
        .from('settings')
        .upsert({ key: 'points_per_referral', value: pointsPerReferralInput.trim() });

      const chanIdErr = await supabase
        .from('settings')
        .upsert({ key: 'private_channel_id', value: privateChannelIdInput.trim() });
        
      const sharingTextErr = await supabase
        .from('settings')
        .upsert({ key: 'sharing_text', value: sharingTextInput.trim() });
        
      if (!thresholdErr.error && !linkErr.error && !pointsErr.error && !chanIdErr.error && !sharingTextErr.error) {
        showFeedback('Sozlamalar saqlandi! ✅', 'success');
        loadSettings();
      } else {
        showFeedback('Saqlashda xatolik yuz berdi', 'error');
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Admin Actions: Toggle Ban
  const handleAdminToggleBan = async (userTgId, currentBanStatus) => {
    const { error } = await supabase
      .from('users')
      .update({ is_banned: !currentBanStatus })
      .eq('telegram_id', userTgId);
      
    if (!error) {
      showFeedback(currentBanStatus ? "Foydalanuvchi blokdan ochildi! 🟢" : "Foydalanuvchi bloklandi! 🔴", 'success');
      loadAdminData();
    }
  };

  // Admin Actions: Increment Referral
  const handleAdminAddReferral = async (userTgId) => {
    const { data: user } = await supabase
      .from('users')
      .select('referral_count, points')
      .eq('telegram_id', userTgId)
      .single();
      
    if (user) {
      const newRef = (user.referral_count || 0) + 1;
      const newPoints = (user.points || 0) + 1;
      
      const { error } = await supabase
        .from('users')
        .update({ referral_count: newRef, points: newPoints })
        .eq('telegram_id', userTgId);
        
      if (!error) {
        showFeedback("+1 taklif qo'shildi!", 'success');
        loadAdminData();
      }
    }
  };

  // Helper: check if user is admin
  const isAdmin = () => {
    return tgUser && adminIds.includes(tgUser.id);
  };

  // Feedback Notification trigger
  const showFeedback = (text, type) => {
    setFeedbackMsg({ text, type });
    triggerHaptic(type === 'success' ? 'success' : 'error');
    setTimeout(() => setFeedbackMsg({ text: '', type: '' }), 4000);
  };

  // Load admin data if tab is active
  useEffect(() => {
    if (activeTab === 'admin') {
      loadAdminData();
    }
  }, [activeTab]);

  const threshold = parseInt(settings.referral_threshold || '5', 10);
  const userReferrals = userData ? Math.max(userData.referral_count || 0, userData.points || 0) : 0;
  const isUnlocked = userReferrals >= threshold;
  const progressPercent = Math.min(100, (userReferrals / threshold) * 100);

  // Filtered users for admin panel search
  const filteredUsers = usersList.filter(u => 
    u.telegram_id.toString().includes(searchTerm) || 
    (u.username && u.username.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (u.first_name && u.first_name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="h-screen max-h-screen overflow-hidden bg-gradient-to-tr from-pink-50 via-rose-50/20 to-indigo-50 text-slate-800 flex flex-col font-sans select-none pb-0 animate-fade-in-up">
      
      {/* SVG Displacement Map for Gooey Droplet filter */}
      {perfClass !== 'low' && (
        <svg className="hidden">
          <defs>
            <filter id="gooey">
              <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
              <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 18 -7" result="goo" />
              <feBlend in="SourceGraphic" in2="goo" />
            </filter>
          </defs>
        </svg>
      )}

      {/* Dynamic Feedback Toast */}
      {feedbackMsg.text && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-2xl shadow-2xl z-50 transition-all duration-300 flex items-center gap-2 text-xs font-semibold border ${
          feedbackMsg.type === 'success' 
            ? 'bg-rose-50 text-rose-700 border-rose-200 shadow-rose-200/50' 
            : 'bg-red-50 text-red-700 border-red-200 shadow-red-200/50'
        }`}>
          {feedbackMsg.type === 'success' ? <CheckCircle size={14} className="text-rose-500" /> : <XCircle size={14} className="text-red-500" />}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* Mock Mode Control Bar */}
      {isMockMode && showDebug && (
        <div className="bg-white/80 border-b border-rose-100 px-4 py-2 flex flex-col gap-2 text-[10px]">
          <div className="flex justify-between items-center text-rose-600 font-bold">
            <span>💻 Brauzer testi: Mock interfeysi faol</span>
            <span>ID: {tgUser?.id}</span>
          </div>
          <div className="flex gap-2">
            <input 
              type="number" 
              placeholder="Telegram ID kiriting" 
              className="bg-rose-50/50 border border-rose-200 px-2.5 py-1 rounded-xl text-slate-800 text-[10px] flex-1 focus:outline-none focus:border-rose-400"
              value={mockId}
              onChange={(e) => setMockId(e.target.value)}
            />
            <button 
              onClick={() => { triggerHaptic(); handleMockSwitch(); }} 
              className="bg-rose-500 text-white font-bold px-3 py-1 rounded-xl hover:bg-rose-400 active:scale-95 transition"
            >
              O'tish
            </button>
          </div>
        </div>
      )}

      {/* Zuhra Olimova Top Title */}
      <div className="px-5 pt-4 pb-1 bg-white/40 backdrop-blur-md flex justify-between items-center border-b border-rose-100/10">
        <span className="text-[10px] font-black tracking-widest bg-gradient-to-r from-pink-500 to-rose-600 bg-clip-text text-transparent uppercase">Zuhra Olimova</span>
        <span className="text-[8px] bg-rose-50 text-rose-500 border border-rose-100 font-extrabold px-2 py-0.5 rounded-full">Yopiq Kurs</span>
      </div>

      {/* Header Profile Section */}
      <header className="px-5 pt-4 pb-4 bg-white/40 backdrop-blur-md border-b border-white/30 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-pink-400 to-rose-400 flex items-center justify-center font-bold text-white shadow-lg shadow-pink-400/20">
            {tgUser?.first_name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="font-bold text-xs leading-tight text-slate-800">{tgUser?.first_name || 'Foydalanuvchi'}</h2>
            <p className="text-[10px] text-pink-600 font-semibold mt-0.5">
              {userData?.is_verified ? '⚡️ Faol ishtirokchi' : '⏳ Kutilmoqda'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 bg-white/85 px-3 py-1.5 rounded-full border border-pink-100 shadow-sm">
          <Sparkles className="text-pink-500 animate-pulse" size={14} />
          <span className="font-extrabold text-xs text-pink-600">{userReferrals} taklif</span>
          <button 
            onClick={() => { triggerHaptic(); loadUser(tgUser.id); }} 
            className="text-slate-400 hover:text-rose-500 transition ml-1"
          >
            <RefreshCw size={11} />
          </button>
        </div>
      </header>

      {/* Main Tab Views */}
      <main className="flex-1 px-4 py-5 overflow-y-auto pb-28 max-w-md mx-auto w-full">
        
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCw className="animate-spin text-pink-500" size={28} />
            <p className="text-[10px] font-bold tracking-wider">Yuklanmoqda...</p>
          </div>
        ) : (
          <>
            {/* Tab: HOME (Referrals & Link) */}
            {activeTab === 'home' && (
              <div className="space-y-5 animate-scale-in">
                
                {/* Status Notice if Unverified */}
                {!userData?.is_verified && !userData?.is_banned && (
                  <div className="bg-white/70 border border-pink-200 p-4 rounded-3xl flex gap-3 text-xs text-pink-700 shadow-md shadow-pink-100/10">
                    <ShieldAlert className="text-pink-500 shrink-0" size={18} />
                    <p className="leading-relaxed">
                      Kursga kirish uchun quyidagi homiy kanallarga obuna bo'lishingiz va a'zolikni tasdiqlashingiz zarur.
                    </p>
                  </div>
                )}

                {/* Dashboard Card (Liquid Glass style) */}
                <div className="bg-white/75 backdrop-blur-xl border border-white/50 p-6 rounded-[32px] relative overflow-hidden shadow-xl shadow-pink-100/25">
                  <div className="absolute -top-10 -right-10 w-32 h-32 bg-pink-300/10 rounded-full blur-2xl" />
                  <div className="absolute -bottom-10 -left-10 w-28 h-28 bg-indigo-300/10 rounded-full blur-2xl" />
                  
                  <p className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Siz taklif qilgan do'stlar</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-4xl font-black text-rose-600">{userReferrals}</span>
                    <span className="text-slate-400 text-xs font-semibold">ta a'zo</span>
                  </div>

                  {/* Custom Progress Bar for Unlock */}
                  <div className="mt-5 space-y-2">
                    <div className="flex justify-between text-[10px] font-bold">
                      <span className="text-slate-500">Kursni ochish holati</span>
                      <span className="text-rose-600">{userReferrals} / {threshold} do'st</span>
                    </div>
                    <div className="w-full h-3 bg-pink-100/60 rounded-full overflow-hidden p-0.5 border border-pink-100">
                      <div 
                        className="h-full bg-gradient-to-r from-pink-400 to-rose-500 rounded-full transition-all duration-500 shadow-inner"
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-6 pt-5 border-t border-rose-100">
                    <div>
                      <p className="text-slate-400 text-[9px] uppercase font-bold tracking-wider">Sizning Status</p>
                      <p className="text-xs font-extrabold text-slate-700 mt-1 flex items-center gap-1">
                        {isUnlocked ? (
                          <>
                            <Unlock size={12} className="text-rose-500" />
                            <span className="text-rose-600">Kurs Ochiq</span>
                          </>
                        ) : (
                          <>
                            <Lock size={12} className="text-slate-400" />
                            <span>Yopiq</span>
                          </>
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-400 text-[9px] uppercase font-bold tracking-wider">Homiy Kanallar</p>
                      <p className="text-xs font-extrabold text-slate-700 mt-1">
                        {userData?.is_verified ? '✅ Ulangan' : '⏳ Kutilmoqda'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Referral Link Box */}
                <div className="bg-white/70 border border-white/40 p-5 rounded-[32px] space-y-4 shadow-lg shadow-pink-100/20">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <img src="/icons/custom_link_emoji.webp" alt="Link" className="w-5 h-5 object-contain inline-block" />
                      <span className="text-xs font-extrabold text-slate-700">Taklif Havolasi</span>
                    </div>
                    <span className="bg-rose-50 text-rose-600 px-2 py-0.5 rounded text-[8px] font-extrabold">Havolangiz</span>
                  </div>
                  <p className="text-slate-400 text-[10px] leading-relaxed">
                    Havolani nusxalang va do'stlaringizga ulashing. Har bir faol a'zo uchun sizga taklif qo'shiladi va yopiq kurs ochiladi!
                  </p>
                  
                  <div className="bg-rose-50/50 border border-rose-100 py-2.5 px-3 rounded-2xl text-center select-all font-mono font-bold text-[10px] text-slate-600 truncate">
                    https://t.me/{import.meta.env.VITE_BOT_USERNAME || 'ranglitugmabot'}?start={tgUser?.id}
                  </div>

                  <div className="flex gap-2">
                    <button 
                      onClick={() => {
                        const link = `https://t.me/${import.meta.env.VITE_BOT_USERNAME || 'ranglitugmabot'}?start=${tgUser?.id}`;
                        navigator.clipboard.writeText(link);
                        triggerHaptic('success');
                        showFeedback('Nusxalandi! 📋', 'success');
                      }}
                      className="flex-1 py-3 px-4 rounded-xl text-xs font-bold bg-white border border-rose-100 hover:bg-rose-50 text-rose-600 flex items-center justify-center gap-1.5 active:scale-95 transition"
                    >
                      <Copy size={13} />
                      <span>Nusxalash</span>
                    </button>
                    <button 
                      onClick={() => {
                        triggerHaptic();
                        const link = `https://t.me/${import.meta.env.VITE_BOT_USERNAME || 'ranglitugmabot'}?start=${tgUser?.id}`;
                        const shareText = settings.sharing_text || "🔥 Zuhra Olimova • Har bir qiz o‘z multfilmini yarata oladi!\n\nBot orqali ro'yxatdan o'ting va yopiq darslarga bepul kiring. Men ham boshladim, sizga ham tavsiya qilaman! 👇";
                        const text = encodeURIComponent(shareText);
                        const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`;
                        const tg = window.Telegram?.WebApp;
                        if (tg?.openTelegramLink) {
                          tg.openTelegramLink(shareUrl);
                        } else {
                          window.open(shareUrl, '_blank');
                        }
                      }}
                      className="flex-1 py-3 px-4 rounded-xl text-xs font-bold bg-rose-500 hover:bg-rose-400 text-white flex items-center justify-center gap-1.5 shadow-md shadow-rose-500/10 active:scale-95 transition"
                    >
                      <ExternalLink size={13} />
                      <span>Do'stlarga ulashish</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab: COURSE ACCESS */}
            {activeTab === 'course' && (
              <div className="space-y-6 flex flex-col items-center py-4 animate-scale-in">
                
                {/* Visual lock status */}
                <div className={`w-20 h-20 rounded-full flex items-center justify-center border shadow-lg ${
                  isUnlocked 
                    ? 'bg-rose-500/10 border-rose-500/20 shadow-rose-500/5 text-rose-600' 
                    : 'bg-slate-100 border-slate-200 shadow-slate-100/5 text-slate-400'
                }`}>
                  {isUnlocked ? <Unlock size={38} className="animate-bounce" /> : <Lock size={38} />}
                </div>
                
                <div className="text-center space-y-2">
                  <h2 className="text-lg font-black text-slate-800">Yopiq Kursga Kirish</h2>
                  <p className="text-[10px] text-slate-400 max-w-[280px] mx-auto leading-relaxed">
                    Siz taklif etgan faol a'zolar kamida **{threshold} ta** bo'lganida kurs joylashgan maxsus kanal eshigi ochiladi.
                  </p>
                </div>

                {/* Progress Details card */}
                <div className="bg-white/70 border border-white/40 p-5 rounded-[32px] w-full text-center shadow-lg shadow-pink-100/20">
                  <p className="text-[9px] text-slate-400 uppercase font-bold tracking-wider">Hozirgi takliflaringiz</p>
                  <p className="text-3xl font-black text-rose-600 mt-1">{userReferrals} / {threshold}</p>
                  <p className="text-[9px] text-slate-400 mt-2">
                    {isUnlocked 
                      ? "Tabriklaymiz! Sizda yetarli a'zolar bor. Quyidagi tugma orqali kursga kirishingiz mumkin." 
                      : `Kursni ochish uchun yana ${threshold - userReferrals} ta do'stingizni taklif qilishingiz kerak.`
                    }
                  </p>
                </div>

                {isUnlocked ? (
                  <a
                    href={settings.private_channel_link || `https://t.me/${import.meta.env.VITE_BOT_USERNAME || 'ranglitugmabot'}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => triggerHaptic('success')}
                    className="w-full py-4 px-6 rounded-2xl font-bold text-xs bg-gradient-to-r from-rose-500 to-pink-500 hover:from-rose-400 hover:to-pink-400 text-white shadow-lg shadow-rose-500/20 hover:shadow-rose-500/35 text-center flex items-center justify-center gap-2 transform active:scale-95 transition"
                  >
                    <span>🔑 Kursga Kirish</span>
                    <ExternalLink size={14} />
                  </a>
                ) : (
                  <button
                    disabled
                    className="w-full py-4 px-6 rounded-2xl font-bold text-xs bg-slate-200 text-slate-400 border border-slate-300/40 cursor-not-allowed text-center flex items-center justify-center gap-2"
                  >
                    <Lock size={14} />
                    <span>Kurs Hali Qulflangan</span>
                  </button>
                )}
              </div>
            )}

            {/* Tab: LEADERBOARD */}
            {activeTab === 'leaderboard' && (
              <div className="space-y-4 animate-scale-in">
                <div className="flex items-center gap-2 pb-1">
                  <Trophy className="text-rose-500" size={18} />
                  <h2 className="text-sm font-extrabold text-slate-800">Eng ko'p do'st taklif qilganlar</h2>
                </div>

                <div className="bg-white/70 border border-white/40 rounded-[32px] overflow-hidden shadow-xl shadow-pink-100/20">
                  {leaderboard.length === 0 ? (
                    <p className="p-6 text-center text-xs text-slate-400 font-medium">Hozircha reyting jadvali bo'sh.</p>
                  ) : (
                    <div className="divide-y divide-rose-50/50">
                      {leaderboard.map((item, index) => {
                        const isTop3 = index < 3;
                        const rankColors = [
                          'bg-amber-100 text-amber-700 border-amber-200',  // Gold
                          'bg-slate-200 text-slate-700 border-slate-300',  // Silver
                          'bg-orange-100 text-orange-700 border-orange-200', // Bronze
                        ];
                        
                        return (
                          <div key={index} className="px-5 py-4 flex items-center justify-between hover:bg-rose-50/10 transition">
                            <div className="flex items-center gap-4">
                              <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-[10px] border ${
                                isTop3 ? rankColors[index] : 'bg-slate-100 text-slate-400 border-slate-200'
                              }`}>
                                {index + 1}
                              </span>
                              <div>
                                <h4 className="font-extrabold text-xs text-slate-700">{maskText(item.first_name)}</h4>
                                {item.username && (
                                  <p className="text-[9px] text-rose-400 font-semibold mt-0.5">@{maskText(item.username)}</p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-1 bg-rose-50 px-2.5 py-1 rounded-full border border-rose-100">
                              <span className="font-extrabold text-xs text-rose-600">{item.referral_count || item.points || 0}</span>
                              <span className="text-[9px] text-rose-400 font-medium">taklif</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tab: ADMIN PANEL */}
            {activeTab === 'admin' && isAdmin() && (
              <div className="space-y-5 animate-scale-in">
                
                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/70 border border-white/40 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[8px] text-slate-400 uppercase font-bold tracking-wider">Jami a'zolar</p>
                    <p className="text-2xl font-black mt-1 text-slate-700">{stats?.total_users || 0}</p>
                  </div>
                  <div className="bg-white/70 border border-white/40 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[8px] text-slate-400 uppercase font-bold tracking-wider">Obunani tekshirganlar</p>
                    <p className="text-2xl font-black mt-1 text-rose-500">{stats?.verified_users || 0}</p>
                  </div>
                  <div className="bg-white/70 border border-white/40 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[8px] text-slate-400 uppercase font-bold tracking-wider">Bloklanganlar (Cheat)</p>
                    <p className="text-2xl font-black mt-1 text-red-500">{stats?.banned_users || 0}</p>
                  </div>
                  <div className="bg-white/70 border border-white/40 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[8px] text-slate-400 uppercase font-bold tracking-wider">Kursni ochganlar</p>
                    <p className="text-2xl font-black mt-1 text-pink-500">{stats?.course_unlocked_users || 0}</p>
                  </div>
                </div>

                {/* Global Settings Configuration */}
                <div className="bg-white/70 border border-white/40 p-5 rounded-[32px] space-y-4 shadow-md">
                  <h3 className="text-xs font-extrabold text-slate-700 flex items-center gap-2">
                    <Settings size={14} className="text-rose-500" />
                    <span>Loyiha Sozlamalari</span>
                  </h3>
                  
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <label className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Minimal Takliflar Chegarasi (Threshold)</label>
                      <input 
                        type="number" 
                        className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                        value={thresholdInput}
                        onChange={(e) => setThresholdInput(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Yopiq Kanal Havolasi (Invite Link Fallback)</label>
                      <input 
                        type="text" 
                        className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                        value={courseLinkInput}
                        onChange={(e) => setCourseLinkInput(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Yopiq Kanal Telegram ID (Private Channel ID)</label>
                      <input 
                        type="text" 
                        className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                        value={privateChannelIdInput}
                        onChange={(e) => setPrivateChannelIdInput(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Har bir taklif uchun ball (Points per Referral)</label>
                      <input 
                        type="number" 
                        className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                        value={pointsPerReferralInput}
                        onChange={(e) => setPointsPerReferralInput(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Taklif Havolasi Ulashilgandagi Matn (Sharing Text)</label>
                      <textarea 
                        className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400 h-24 resize-none"
                        value={sharingTextInput}
                        onChange={(e) => setSharingTextInput(e.target.value)}
                      />
                    </div>
                    <button
                      onClick={handleSaveSettings}
                      className="bg-rose-500 hover:bg-rose-400 w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white transition shadow-md shadow-rose-500/10"
                    >
                      Sozlamalarni Saqlash
                    </button>
                  </div>
                </div>

                {/* Force Subscribe Channels Settings */}
                <div className="bg-white/70 border border-white/40 p-5 rounded-[32px] space-y-4 shadow-md">
                  <h3 className="text-xs font-extrabold text-slate-700 flex items-center gap-2">
                    <PlusCircle size={14} className="text-rose-500" />
                    <span>Majburiy Kanallar</span>
                  </h3>
                  
                  {/* Channels List */}
                  <div className="space-y-2">
                    {activeChannels.map(ch => (
                      <div key={ch.id} className="bg-rose-50/30 border border-rose-100 px-3 py-2.5 rounded-xl flex items-center justify-between">
                        <div className="text-[10px] truncate max-w-[180px]">
                          <p className="font-extrabold text-slate-700">{ch.title}</p>
                          <p className="text-[8px] font-mono text-slate-400">{ch.tg_id}</p>
                        </div>
                        <button 
                          onClick={() => handleAdminDelChannel(ch.id)}
                          className="text-red-500 hover:text-red-400 p-1 bg-red-500/5 border border-red-500/10 rounded-lg transition"
                        >
                          <Trash size={11} />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Add Channel Form */}
                  <div className="space-y-2 pt-2 border-t border-rose-100">
                    <input 
                      type="number" 
                      placeholder="Telegram Chat ID (e.g. -100...)" 
                      className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                      value={adminChannelId}
                      onChange={(e) => setAdminChannelId(e.target.value)}
                    />
                    <input 
                      type="text" 
                      placeholder="Kanal nomi (Title)" 
                      className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                      value={adminChannelTitle}
                      onChange={(e) => setAdminChannelTitle(e.target.value)}
                    />
                    <input 
                      type="text" 
                      placeholder="Havola (Invite Link)" 
                      className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                      value={adminChannelLink}
                      onChange={(e) => setAdminChannelLink(e.target.value)}
                    />
                    <button
                      onClick={handleAdminAddChannel}
                      className="bg-rose-500 hover:bg-rose-400 w-full py-2.5 px-4 rounded-xl text-xs font-bold text-white transition shadow-md shadow-rose-500/10"
                    >
                      Kanal Qo'shish
                    </button>
                  </div>
                </div>

                {/* User Manager Console */}
                <div className="bg-white/70 border border-white/40 p-5 rounded-[32px] space-y-4 shadow-md">
                  <h3 className="text-xs font-extrabold text-slate-700 flex items-center gap-2">
                    <User size={14} className="text-rose-500" />
                    <span>Foydalanuvchilarni Boshqarish</span>
                  </h3>
                  
                  <input 
                    type="text"
                    placeholder="Qidirish (ID, Ism, Username)"
                    className="bg-rose-50/50 border border-rose-100 rounded-xl px-3 py-2 text-xs w-full text-slate-700 focus:outline-none focus:border-rose-400"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />

                  <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                    {filteredUsers.length === 0 ? (
                      <p className="text-center text-xs text-slate-400 py-4">Foydalanuvchilar topilmadi.</p>
                    ) : (
                      filteredUsers.slice(0, 50).map(u => (
                        <div key={u.id} className="bg-rose-50/20 border border-rose-100/50 p-3 rounded-2xl space-y-2 shadow-inner">
                          <div className="flex justify-between items-start text-[10px]">
                            <div>
                              <p className="font-extrabold text-slate-700">{u.first_name} {u.last_name || ''}</p>
                              <p className="font-mono text-[8px] text-slate-400">@{u.username || 'yo\'q'} • ID: {u.telegram_id}</p>
                            </div>
                            <span className={`px-2 py-0.5 rounded border text-[8px] font-bold ${
                              u.is_banned 
                                ? 'text-red-600 bg-red-50 border-red-200' 
                                : u.is_verified 
                                  ? 'text-rose-600 bg-rose-50 border-rose-200' 
                                  : 'text-slate-500 bg-slate-50 border-slate-200'
                            }`}>
                              {u.is_banned ? 'BANNED' : u.is_verified ? 'VERIFIED' : 'PENDING'}
                            </span>
                          </div>
                          
                          <div className="flex justify-between items-center text-[10px] pt-1">
                            <span className="text-slate-500">Taklif etilgan do'stlar:</span>
                            <span className="font-black text-rose-600">{Math.max(u.referral_count || 0, u.points || 0)} ta</span>
                          </div>

                          {/* Inviter Info */}
                          {u.referred_by && (
                            <div className="flex justify-between items-center text-[9px] text-slate-400 pt-0.5">
                              <span>Kim taklif qilgan:</span>
                              <span className="font-semibold text-slate-500">
                                {(() => {
                                  const inviter = usersList.find(x => x.telegram_id === u.referred_by);
                                  return inviter ? `${inviter.first_name} (@${inviter.username || 'yo\'q'})` : `ID: ${u.referred_by}`;
                                })()}
                              </span>
                            </div>
                          )}

                          {/* Invitees Info */}
                          {(() => {
                            const referrals = usersList.filter(x => x.referred_by === u.telegram_id);
                            if (referrals.length > 0) {
                              return (
                                <div className="text-[9px] text-slate-400 bg-rose-50/20 p-2 rounded-xl border border-rose-100/30 mt-1 space-y-1">
                                  <p className="font-extrabold text-[8px] text-slate-500 uppercase tracking-wide">Taklif qilgan a'zolari ({referrals.length} ta):</p>
                                  <p className="truncate font-medium text-slate-600">
                                    {referrals.map(r => `${r.first_name} (${r.username ? '@' + r.username : 'ID: ' + r.telegram_id})`).join(', ')}
                                  </p>
                                </div>
                              );
                            }
                            return null;
                          })()}

                          <div className="flex gap-2 pt-1 border-t border-rose-100/50">
                            <button
                              onClick={() => handleAdminAddReferral(u.telegram_id)}
                              className="bg-rose-500 hover:bg-rose-400 text-white font-bold py-1 px-2.5 rounded-lg text-[9px] flex-1 active:scale-95 transition"
                            >
                              +1 Taklif Qo'shish
                            </button>
                            <button
                              onClick={() => handleAdminToggleBan(u.telegram_id, u.is_banned)}
                              className={`font-bold py-1 px-2.5 rounded-lg text-[9px] flex-1 active:scale-95 transition border ${
                                u.is_banned 
                                  ? 'bg-emerald-500 hover:bg-emerald-400 text-white border-emerald-600/10' 
                                  : 'bg-red-500 hover:bg-red-400 text-white border-red-600/10'
                              }`}
                            >
                              {u.is_banned ? 'Blokdan ochish' : 'Bloklash'}
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>
            )}
          </>
        )}
      </main>

      {/* Footer Navigation Bar (Themed Pink & Spatially Aware) */}
      <footer className="fixed bottom-4 left-4 right-4 max-w-md mx-auto bg-white/75 backdrop-blur-xl border border-white/60 px-4 py-1.5 flex justify-around items-center shadow-lg shadow-pink-100/30 z-40 rounded-2xl">
        <button 
          onClick={() => { triggerHaptic(); setActiveTab('home'); }} 
          className="relative py-1 px-3.5 flex flex-col items-center gap-0.5 transition-all duration-300 active:scale-90"
        >
          <div className={`absolute inset-0 rounded-xl transition-all duration-300 -z-10 ${
            activeTab === 'home' ? 'bg-rose-50 border border-rose-100/40 scale-100 opacity-100 shadow-sm shadow-rose-100/10' : 'scale-75 opacity-0'
          }`} />
          <User size={15} className={`transition-all duration-300 ${activeTab === 'home' ? 'text-rose-600 scale-110' : 'text-slate-400'}`} />
          <span className={`text-[9px] transition-all duration-300 font-bold ${activeTab === 'home' ? 'text-rose-600' : 'text-slate-400'}`}>Profil</span>
        </button>
        
        <button 
          onClick={() => { triggerHaptic(); setActiveTab('course'); }} 
          className="relative py-1 px-3.5 flex flex-col items-center gap-0.5 transition-all duration-300 active:scale-90"
        >
          <div className={`absolute inset-0 rounded-xl transition-all duration-300 -z-10 ${
            activeTab === 'course' ? 'bg-rose-50 border border-rose-100/40 scale-100 opacity-100 shadow-sm shadow-rose-100/10' : 'scale-75 opacity-0'
          }`} />
          <BookOpen size={15} className={`transition-all duration-300 ${activeTab === 'course' ? 'text-rose-600 scale-110' : 'text-slate-400'}`} />
          <span className={`text-[9px] transition-all duration-300 font-bold ${activeTab === 'course' ? 'text-rose-600' : 'text-slate-400'}`}>Kurs</span>
        </button>

        <button 
          onClick={() => { triggerHaptic(); setActiveTab('leaderboard'); }} 
          className="relative py-1 px-3.5 flex flex-col items-center gap-0.5 transition-all duration-300 active:scale-90"
        >
          <div className={`absolute inset-0 rounded-xl transition-all duration-300 -z-10 ${
            activeTab === 'leaderboard' ? 'bg-rose-50 border border-rose-100/40 scale-100 opacity-100 shadow-sm shadow-rose-100/10' : 'scale-75 opacity-0'
          }`} />
          <Trophy size={15} className={`transition-all duration-300 ${activeTab === 'leaderboard' ? 'text-rose-600 scale-110' : 'text-slate-400'}`} />
          <span className={`text-[9px] transition-all duration-300 font-bold ${activeTab === 'leaderboard' ? 'text-rose-600' : 'text-slate-400'}`}>Reyting</span>
        </button>

        {isAdmin() && (
          <button 
            onClick={() => { triggerHaptic(); setActiveTab('admin'); }} 
            className="relative py-1 px-3.5 flex flex-col items-center gap-0.5 transition-all duration-300 active:scale-90"
          >
            <div className={`absolute inset-0 rounded-xl transition-all duration-300 -z-10 ${
              activeTab === 'admin' ? 'bg-rose-50 border border-rose-100/40 scale-100 opacity-100 shadow-sm shadow-rose-100/10' : 'scale-75 opacity-0'
            }`} />
            <Settings size={15} className={`transition-all duration-300 ${activeTab === 'admin' ? 'text-rose-600 scale-110' : 'text-slate-400'}`} />
            <span className={`text-[9px] transition-all duration-300 font-bold ${activeTab === 'admin' ? 'text-rose-600' : 'text-slate-400'}`}>Admin</span>
          </button>
        )}
      </footer>
      
    </div>
  );
}
