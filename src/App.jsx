import React, { useState, useEffect } from 'react';
import { 
  User, Coins, Gift, Users, Wallet, Trophy, Settings, 
  RefreshCw, BarChart2, ShieldAlert, CheckCircle, XCircle, 
  ArrowRightLeft, Copy, Clock, Send, PlusCircle, Trash, ExternalLink
} from 'lucide-react';
import { supabase } from './supabase_client';

export default function App() {
  // Telegram WebApp API Integration
  const [tgUser, setTgUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [userData, setUserData] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [activeChannels, setActiveChannels] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [stats, setStats] = useState(null);
  const [settings, setSettings] = useState({});
  
  // App navigation state: 'home' | 'bonus' | 'leaderboard' | 'wallet' | 'admin'
  const [activeTab, setActiveTab] = useState('home');
  
  // Custom mock ID for development/testing in standard browsers
  const [mockId, setMockId] = useState('');
  const [isMockMode, setIsMockMode] = useState(false);
  
  // Inputs
  const [walletInput, setWalletInput] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [adminChannelId, setAdminChannelId] = useState('');
  const [adminChannelTitle, setAdminChannelTitle] = useState('');
  const [adminChannelLink, setAdminChannelLink] = useState('');
  
  // UI states
  const [feedbackMsg, setFeedbackMsg] = useState({ text: '', type: '' });
  const [isClaiming, setIsClaiming] = useState(false);
  const [countdown, setCountdown] = useState('');

  // Admin IDs list
  const adminIds = (import.meta.env.VITE_ADMIN_IDS || '8544023815')
    .split(',')
    .map(id => parseInt(id.trim(), 10));

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.initDataUnsafe?.user) {
        setTgUser(tg.initDataUnsafe.user);
        loadUser(tg.initDataUnsafe.user.id, tg.initDataUnsafe.user);
      } else {
        setIsMockMode(true);
        const defaultMock = 8544023815;
        setTgUser({ id: defaultMock, first_name: 'Mock User', username: 'mock_user' });
        loadUser(defaultMock, { first_name: 'Mock User', username: 'mock_user' });
      }
    } else {
      setIsMockMode(true);
      const defaultMock = 8544023815;
      setTgUser({ id: defaultMock, first_name: 'Mock User', username: 'mock_user' });
      loadUser(defaultMock, { first_name: 'Mock User', username: 'mock_user' });
    }
    
    loadLeaderboard();
    loadSettings();
  }, []);

  // Update countdown timer for Daily Bonus
  useEffect(() => {
    if (!userData?.last_bonus_claim) return;
    
    const interval = setInterval(() => {
      const lastClaim = new Date(userData.last_bonus_claim);
      const nextClaim = new Date(lastClaim.getTime() + 24 * 60 * 60 * 1000);
      const now = new Date();
      const diff = nextClaim - now;
      
      if (diff <= 0) {
        setCountdown('');
        clearInterval(interval);
      } else {
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        setCountdown(`${hours}s ${minutes}m ${seconds}s`);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [userData?.last_bonus_claim]);

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
            wallet: null,
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
            setWalletInput('');
          } else {
            setUserData(newUser);
          }
        } else {
          showFeedback('Xatolik yuz berdi: ' + error.message, 'error');
        }
      } else {
        setUserData(data);
        setWalletInput(data.wallet || '');
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
      .select('first_name, username, points')
      .eq('is_banned', false)
      .order('points', { ascending: false })
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
    }
  };

  // Load Admin Data (Withdrawals, Channels, General Stats)
  const loadAdminData = async () => {
    if (!isAdmin()) return;
    
    // Load channels
    const { data: chs } = await supabase
      .from('channels')
      .select('*');
    if (chs) setActiveChannels(chs);
    
    // Load withdrawals
    const { data: wds } = await supabase
      .from('withdrawals')
      .select('*, users(first_name, username, points)')
      .order('created_at', { ascending: false });
    if (wds) setWithdrawals(wds);
    
    // Load statistics
    const { data: usersCount } = await supabase.from('users').select('is_banned, is_verified');
    const { data: wdsList } = await supabase.from('withdrawals').select('status, amount');
    
    if (usersCount) {
      const total = usersCount.length;
      const verified = usersCount.filter(u => u.is_verified).length;
      const banned = usersCount.filter(u => u.is_banned).length;
      
      let totalApproved = 0;
      let pending = 0;
      if (wdsList) {
        wdsList.forEach(w => {
          if (w.status === 'approved') totalApproved += parseFloat(w.amount);
          else if (w.status === 'pending') pending++;
        });
      }
      
      setStats({
        total_users: total,
        verified_users: verified,
        banned_users: banned,
        total_withdrawn: totalApproved,
        pending_withdrawals: pending
      });
    }
  };

  // Bind Wallet Address
  const handleSaveWallet = async () => {
    if (!walletInput.trim()) {
      showFeedback('Hamyon manzilini kiriting!', 'error');
      return;
    }
    
    if (walletInput.length < 20) {
      showFeedback('Tegishli hamyon manzilini kiriting (TRX/USDT)!', 'error');
      return;
    }

    const { error } = await supabase
      .from('users')
      .update({ wallet: walletInput.trim() })
      .eq('telegram_id', tgUser.id);
      
    if (!error) {
      setUserData({ ...userData, wallet: walletInput.trim() });
      showFeedback('Hamyon manzili bog\'landi! ✅', 'success');
    } else {
      showFeedback('Saqlashda xatolik: ' + error.message, 'error');
    }
  };

  // Submit Withdrawal Request
  const handleRequestWithdraw = async () => {
    const amountNum = parseFloat(withdrawAmount);
    const minPoints = parseInt(settings.min_withdrawal_points || '5', 10);
    
    if (isNaN(amountNum) || amountNum <= 0) {
      showFeedback('To\'g\'ri miqdor kiriting!', 'error');
      return;
    }
    
    if (amountNum < minPoints) {
      showFeedback(`Minimal pul yechish: ${minPoints} ball!`, 'error');
      return;
    }
    
    if (amountNum > userData.points) {
      showFeedback('Mablag\' yetarli emas!', 'error');
      return;
    }
    
    if (!userData.wallet) {
      showFeedback('Hamyon manzilini bog\'lang!', 'error');
      return;
    }

    // Deduct points
    const { error: updateErr } = await supabase
      .from('users')
      .update({ points: userData.points - amountNum })
      .eq('telegram_id', tgUser.id);
      
    if (updateErr) {
      showFeedback('Xatolik: ' + updateErr.message, 'error');
      return;
    }

    // Insert withdrawal
    const { error: insertErr } = await supabase
      .from('withdrawals')
      .insert([
        {
          tg_id: tgUser.id,
          wallet: userData.wallet,
          amount: amountNum,
          status: 'pending'
        }
      ]);
      
    if (!insertErr) {
      setUserData({ ...userData, points: userData.points - amountNum });
      setWithdrawAmount('');
      showFeedback('So\'rov yuborildi! Tekshiruvdan so\'ng to\'lanadi. 💸', 'success');
      loadUser(tgUser.id);
    } else {
      showFeedback('So\'rov yuborishda xatolik: ' + insertErr.message, 'error');
    }
  };

  // Claim Daily Bonus
  const handleClaimBonus = async () => {
    if (countdown) {
      showFeedback('Siz bugungi bonusni olgansiz!', 'error');
      return;
    }
    
    setIsClaiming(true);
    try {
      const now = new Date();
      const bonusPts = parseInt(settings.daily_bonus_points || '1', 10);
      const newPoints = (userData.points || 0) + bonusPts;
      
      const { error } = await supabase
        .from('users')
        .update({
          points: newPoints,
          last_bonus_claim: now.toISOString()
        })
        .eq('telegram_id', tgUser.id);
        
      if (!error) {
        setUserData({
          ...userData,
          points: newPoints,
          last_bonus_claim: now.toISOString()
        });
        showFeedback(`Tabriklaymiz! +${bonusPts} ball berildi! 🎉`, 'success');
      } else {
        showFeedback('Bonus olishda xatolik: ' + error.message, 'error');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsClaiming(false);
    }
  };

  // Admin Actions: Approve/Reject Withdrawal
  const handleAdminWithdraw = async (wId, status, userTgId, amount) => {
    const { error } = await supabase
      .from('withdrawals')
      .update({ status: status })
      .eq('id', wId);
      
    if (!error) {
      showFeedback(`So'rov #${wId} '${status}' holatiga o'tkazildi!`, 'success');
      
      // If rejected, refund user points
      if (status === 'rejected') {
        const { data: user } = await supabase
          .from('users')
          .select('points')
          .eq('telegram_id', userTgId)
          .single();
          
        if (user) {
          await supabase
            .from('users')
            .update({ points: user.points + amount })
            .eq('telegram_id', userTgId);
        }
      }
      
      loadAdminData();
    } else {
      showFeedback('Xatolik: ' + error.message, 'error');
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

  // Helper: check if user is admin
  const isAdmin = () => {
    return tgUser && adminIds.includes(tgUser.id);
  };

  // Feedback Notification trigger
  const showFeedback = (text, type) => {
    setFeedbackMsg({ text, type });
    setTimeout(() => setFeedbackMsg({ text: '', type: '' }), 4000);
  };

  // Load admin data if tab is active
  useEffect(() => {
    if (activeTab === 'admin') {
      loadAdminData();
    }
  }, [activeTab]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none pb-20 animate-fade-in-up">
      
      {/* Dynamic Feedback Toast */}
      {feedbackMsg.text && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-xl shadow-2xl z-50 transition-all duration-300 flex items-center gap-2 text-sm font-semibold border ${
          feedbackMsg.type === 'success' 
            ? 'bg-emerald-950/90 text-emerald-400 border-emerald-500/30' 
            : 'bg-rose-950/90 text-rose-400 border-rose-500/30'
        }`}>
          {feedbackMsg.type === 'success' ? <CheckCircle size={18} /> : <XCircle size={18} />}
          <span>{feedbackMsg.text}</span>
        </div>
      )}

      {/* Mock Mode Control Bar */}
      {isMockMode && (
        <div className="bg-amber-950/70 border-b border-amber-500/20 px-4 py-2 flex flex-col gap-2 text-xs">
          <div className="flex justify-between items-center text-amber-400">
            <span>💻 Brauzer testi: Mock interfeysi faol</span>
            <span>ID: {tgUser?.id}</span>
          </div>
          <div className="flex gap-2">
            <input 
              type="number" 
              placeholder="Telegram ID kiriting" 
              className="bg-slate-900 border border-amber-500/30 px-2 py-1 rounded text-white text-xs flex-1 focus:outline-none"
              value={mockId}
              onChange={(e) => setMockId(e.target.value)}
            />
            <button 
              onClick={handleMockSwitch} 
              className="bg-amber-500 text-slate-950 font-bold px-3 py-1 rounded hover:bg-amber-400 transition"
            >
              Almashtirish
            </button>
          </div>
        </div>
      )}

      {/* Header Profile Section */}
      <header className="px-5 pt-6 pb-4 bg-slate-900/40 backdrop-blur-md border-b border-slate-900 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 to-cyan-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
            {tgUser?.first_name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="font-bold text-sm leading-tight">{tgUser?.first_name || 'Foydalanuvchi'}</h2>
            <p className="text-xs text-indigo-400 font-medium">
              {userData?.is_verified ? '⚡️ Tasdiqlangan ishtirokchi' : '⏳ Kutilmoqda'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-full border border-slate-800 shadow-inner">
          <Coins className="text-amber-400 animate-pulse" size={16} />
          <span className="font-bold text-sm text-amber-400">{userData ? userData.points : 0} ball</span>
          <button 
            onClick={() => loadUser(tgUser.id)} 
            className="text-slate-400 hover:text-white transition ml-1"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      </header>

      {/* Main Tab Views */}
      <main className="flex-1 px-4 py-5 overflow-y-auto max-w-md mx-auto w-full">
        
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCw className="animate-spin text-indigo-500" size={32} />
            <p className="text-xs font-semibold">Yuklanmoqda...</p>
          </div>
        ) : (
          <>
            {/* Tab: HOME (Referrals & Link) */}
            {activeTab === 'home' && (
              <div className="space-y-5 animate-scale-in">
                
                {/* Status Notice if Unverified */}
                {!userData?.is_verified && !userData?.is_banned && (
                  <div className="bg-indigo-950/30 border border-indigo-500/20 p-4 rounded-2xl flex gap-3 text-sm text-indigo-300">
                    <ShieldAlert className="text-indigo-400 shrink-0" size={20} />
                    <p className="text-xs leading-relaxed">
                      Sizning profilingiz hali to'liq tasdiqlanmagan. Botdagi homiy kanallarga obuna bo'ling va ballar olishni boshlang!
                    </p>
                  </div>
                )}

                {/* Dashboard Card */}
                <div className="bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-900 p-6 rounded-3xl relative overflow-hidden shadow-2xl">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-3xl" />
                  <div className="absolute bottom-0 left-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl" />
                  
                  <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">Jamg'arilgan Ball</p>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-4xl font-extrabold text-white">{userData?.points || 0}</span>
                    <span className="text-slate-400 text-sm font-semibold">ball</span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-slate-900">
                    <div>
                      <p className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Taklif Turi</p>
                      <p className="text-sm font-bold text-slate-200 mt-0.5">{userData?.referred_by ? 'Taklif qilingan' : 'Direct'}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 text-[10px] uppercase font-bold tracking-wider">Hamyon</p>
                      <p className="text-xs font-mono font-medium text-slate-200 mt-1 truncate max-w-[120px]">
                        {userData?.wallet || 'Kiritilmagan'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Referral Link Box */}
                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl space-y-3">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <Users className="text-indigo-400" size={18} />
                      <span className="text-sm font-bold text-slate-200">Taklif Havolasi</span>
                    </div>
                    <span className="bg-indigo-950 text-indigo-400 px-2 py-0.5 rounded text-[10px] font-extrabold">Taklif qiling</span>
                  </div>
                  <p className="text-slate-400 text-xs leading-relaxed">
                    Ushbu havola orqali do'stlaringizni botga taklif qiling. Ular obunalarni tasdiqlaganida sizga ball yoziladi.
                  </p>
                  <div className="flex gap-2 bg-slate-950 border border-slate-900 p-1.5 rounded-2xl">
                    <span className="text-xs text-slate-400 select-all truncate px-2 flex-1 self-center font-mono">
                      https://t.me/{import.meta.env.VITE_BOT_USERNAME || 'hammagayetadi_bot'}?start={tgUser?.id}
                    </span>
                    <button 
                      onClick={() => {
                        const link = `https://t.me/${import.meta.env.VITE_BOT_USERNAME || 'hammagayetadi_bot'}?start=${tgUser?.id}`;
                        navigator.clipboard.writeText(link);
                        showFeedback('Nusxalandi! 📋', 'success');
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-bold p-2.5 rounded-xl transition"
                    >
                      <Copy size={16} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab: DAILY BONUS */}
            {activeTab === 'bonus' && (
              <div className="space-y-6 flex flex-col items-center py-4 animate-scale-in">
                <div className="w-20 h-20 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shadow-lg shadow-amber-500/5">
                  <Gift className="text-amber-500" size={40} />
                </div>
                
                <div className="text-center space-y-2">
                  <h2 className="text-xl font-bold">Kunlik Bepul Bonus</h2>
                  <p className="text-xs text-slate-400 max-w-[280px] mx-auto leading-relaxed">
                    Har 24 soatda bir marta botimizdan bepul bonus ballaringizni claim qiling va balansingizni oshiring!
                  </p>
                </div>

                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl w-full text-center">
                  <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Bonus Miqdori</p>
                  <p className="text-3xl font-black text-amber-400 mt-1">+{settings.daily_bonus_points || 1} ball</p>
                </div>

                <button
                  onClick={handleClaimBonus}
                  disabled={!!countdown || isClaiming}
                  className={`w-full py-4 px-6 rounded-2xl font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 ${
                    countdown 
                      ? 'bg-slate-900 border border-slate-800 text-slate-500 cursor-not-allowed' 
                      : 'bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 active:scale-95 text-white'
                  }`}
                >
                  {isClaiming ? (
                    <RefreshCw className="animate-spin" size={18} />
                  ) : countdown ? (
                    <>
                      <Clock size={18} />
                      <span>{countdown} qoldi</span>
                    </>
                  ) : (
                    <span>Bonusni olish 🎁</span>
                  )}
                </button>
              </div>
            )}

            {/* Tab: LEADERBOARD */}
            {activeTab === 'leaderboard' && (
              <div className="space-y-4 animate-scale-in">
                <div className="flex items-center gap-2.5 pb-2">
                  <Trophy className="text-amber-400" size={20} />
                  <h2 className="text-lg font-bold">TOP 10 Ishtirokchilar</h2>
                </div>

                <div className="bg-slate-900/30 border border-slate-900 rounded-3xl overflow-hidden shadow-xl">
                  {leaderboard.length === 0 ? (
                    <p className="p-6 text-center text-xs text-slate-500 font-medium">Hozircha reyting jadvali bo'sh.</p>
                  ) : (
                    <div className="divide-y divide-slate-900">
                      {leaderboard.map((item, index) => {
                        const isTop3 = index < 3;
                        const rankColors = [
                          'bg-amber-400 text-slate-950', // Gold
                          'bg-slate-300 text-slate-950', // Silver
                          'bg-amber-700 text-white',      // Bronze
                        ];
                        
                        return (
                          <div key={index} className="px-5 py-4 flex items-center justify-between hover:bg-slate-900/10 transition">
                            <div className="flex items-center gap-4">
                              <span className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                                isTop3 ? rankColors[index] : 'bg-slate-950 text-slate-400'
                              }`}>
                                {index + 1}
                              </span>
                              <div>
                                <h4 className="font-bold text-sm text-slate-100">{item.first_name}</h4>
                                {item.username && (
                                  <p className="text-[10px] text-indigo-400 font-medium">@{item.username}</p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <span className="font-extrabold text-sm text-amber-400">{item.points}</span>
                              <span className="text-[10px] text-slate-400 font-medium">ball</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tab: WALLET & CASH OUT */}
            {activeTab === 'wallet' && (
              <div className="space-y-5 animate-scale-in">
                
                {/* Wallet binding form */}
                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl space-y-4">
                  <div className="flex items-center gap-2">
                    <Wallet className="text-indigo-400" size={18} />
                    <h3 className="text-sm font-bold text-slate-200">Hamyonni bog'lash</h3>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">USDT (TRC20) yoki TRX manzil</label>
                    <div className="flex gap-2">
                      <input 
                        type="text" 
                        placeholder="Masalan: TR7NHqjeKQxGTC..." 
                        className="bg-slate-950 border border-slate-900 focus:border-indigo-500/50 rounded-2xl px-4 py-3 text-xs w-full text-slate-100 font-mono focus:outline-none transition"
                        value={walletInput}
                        onChange={(e) => setWalletInput(e.target.value)}
                      />
                      <button
                        onClick={handleSaveWallet}
                        className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-xs font-bold px-4 py-3 rounded-2xl transition"
                      >
                        Saqlash
                      </button>
                    </div>
                  </div>
                </div>

                {/* Withdrawal request form */}
                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl space-y-4">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <ArrowRightLeft className="text-emerald-400" size={18} />
                      <h3 className="text-sm font-bold text-slate-200">Pul yechib olish</h3>
                    </div>
                    <span className="text-[10px] text-slate-400 font-medium">Minimal: {settings.min_withdrawal_points || 5} ball</span>
                  </div>

                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Miqdorni kiriting (Ball)</label>
                      <input 
                        type="number" 
                        placeholder={`Min: ${settings.min_withdrawal_points || 5}`} 
                        className="bg-slate-950 border border-slate-900 focus:border-emerald-500/50 rounded-2xl px-4 py-3 text-xs w-full text-slate-100 font-medium focus:outline-none transition"
                        value={withdrawAmount}
                        onChange={(e) => setWithdrawAmount(e.target.value)}
                      />
                    </div>

                    <button
                      onClick={handleRequestWithdraw}
                      disabled={!userData?.wallet}
                      className={`w-full py-3 px-4 rounded-2xl font-bold text-xs transition-all flex items-center justify-center gap-2 ${
                        !userData?.wallet 
                          ? 'bg-slate-900 border border-slate-800 text-slate-500 cursor-not-allowed'
                          : 'bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white shadow-lg shadow-emerald-600/10'
                      }`}
                    >
                      <Send size={14} />
                      <span>So'rov yuborish</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab: ADMIN PANEL */}
            {activeTab === 'admin' && isAdmin() && (
              <div className="space-y-5 animate-scale-in">
                
                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-900/30 border border-slate-900 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[9px] text-slate-400 uppercase font-bold tracking-wider">Jami a'zolar</p>
                    <p className="text-2xl font-black mt-1 text-slate-200">{stats?.total_users || 0}</p>
                  </div>
                  <div className="bg-slate-900/30 border border-slate-900 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[9px] text-slate-400 uppercase font-bold tracking-wider">Faol/Verified</p>
                    <p className="text-2xl font-black mt-1 text-emerald-400">{stats?.verified_users || 0}</p>
                  </div>
                  <div className="bg-slate-900/30 border border-slate-900 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[9px] text-slate-400 uppercase font-bold tracking-wider">Bloklanganlar (Cheat)</p>
                    <p className="text-2xl font-black mt-1 text-rose-400">{stats?.banned_users || 0}</p>
                  </div>
                  <div className="bg-slate-900/30 border border-slate-900 p-4 rounded-2xl text-center shadow-md">
                    <p className="text-[9px] text-slate-400 uppercase font-bold tracking-wider">To'langan summa</p>
                    <p className="text-2xl font-black mt-1 text-amber-400">{stats?.total_withdrawn || 0}</p>
                  </div>
                </div>

                {/* Force Subscribe Channels Settings */}
                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl space-y-4 shadow-md">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <PlusCircle size={16} className="text-indigo-400" />
                    <span>Majburiy Kanallar</span>
                  </h3>
                  
                  {/* Channels List */}
                  <div className="space-y-2">
                    {activeChannels.map(ch => (
                      <div key={ch.id} className="bg-slate-950 border border-slate-900 px-3 py-2.5 rounded-xl flex items-center justify-between">
                        <div className="text-xs truncate max-w-[180px]">
                          <p className="font-bold text-slate-200">{ch.title}</p>
                          <p className="text-[9px] font-mono text-slate-400">{ch.tg_id}</p>
                        </div>
                        <button 
                          onClick={() => handleAdminDelChannel(ch.id)}
                          className="text-rose-500 hover:text-rose-400 p-1 bg-rose-500/5 border border-rose-500/10 rounded-lg transition"
                        >
                          <Trash size={12} />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Add Channel Form */}
                  <div className="space-y-2 pt-2 border-t border-slate-900">
                    <input 
                      type="number" 
                      placeholder="Telegram Chat ID (e.g. -100...)" 
                      className="bg-slate-950 border border-slate-900 rounded-xl px-3 py-2 text-xs w-full text-slate-200 focus:outline-none"
                      value={adminChannelId}
                      onChange={(e) => setAdminChannelId(e.target.value)}
                    />
                    <input 
                      type="text" 
                      placeholder="Kanal nomi (Title)" 
                      className="bg-slate-950 border border-slate-900 rounded-xl px-3 py-2 text-xs w-full text-slate-200 focus:outline-none"
                      value={adminChannelTitle}
                      onChange={(e) => setAdminChannelTitle(e.target.value)}
                    />
                    <input 
                      type="text" 
                      placeholder="Havola (Invite Link)" 
                      className="bg-slate-950 border border-slate-900 rounded-xl px-3 py-2 text-xs w-full text-slate-200 focus:outline-none"
                      value={adminChannelLink}
                      onChange={(e) => setAdminChannelLink(e.target.value)}
                    />
                    <button
                      onClick={handleAdminAddChannel}
                      className="bg-indigo-600 hover:bg-indigo-500 w-full py-2.5 px-4 rounded-xl text-xs font-bold transition text-white"
                    >
                      Kanal Qo'shish
                    </button>
                  </div>
                </div>

                {/* Pending Withdrawals Approval Panel */}
                <div className="bg-slate-900/30 border border-slate-900 p-5 rounded-3xl space-y-4 shadow-md">
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <ArrowRightLeft size={16} className="text-emerald-400" />
                    <span>Pul yechish so'rovlari ({withdrawals.filter(w => w.status === 'pending').length})</span>
                  </h3>

                  <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
                    {withdrawals.length === 0 ? (
                      <p className="text-center text-xs text-slate-500 py-4">Pul yechish so'rovlari yo'q.</p>
                    ) : (
                      withdrawals.map(w => {
                        const statusColors = {
                          pending: 'text-amber-400 bg-amber-400/5 border-amber-500/20',
                          approved: 'text-emerald-400 bg-emerald-400/5 border-emerald-500/20',
                          rejected: 'text-rose-400 bg-rose-400/5 border-rose-500/20'
                        };
                        
                        return (
                          <div key={w.id} className="bg-slate-950 border border-slate-900 p-3 rounded-2xl space-y-2 shadow-inner">
                            <div className="flex justify-between items-start text-[10px]">
                              <div>
                                <p className="font-bold text-slate-200">
                                  {w.users?.first_name || 'Ishtirokchi'} (@{w.users?.username || 'yo\'q'})
                                </p>
                                <p className="font-mono text-[8px] text-slate-400">ID: {w.tg_id} • #{w.id}</p>
                              </div>
                              <span className={`px-2 py-0.5 rounded border text-[8px] font-bold ${statusColors[w.status]}`}>
                                {w.status.toUpperCase()}
                              </span>
                            </div>
                            
                            <div className="flex justify-between items-center pt-1">
                              <div>
                                <p className="text-[9px] text-slate-400">Hamyon:</p>
                                <p className="font-mono text-[10px] text-slate-300 max-w-[180px] truncate">{w.wallet}</p>
                              </div>
                              <p className="text-sm font-black text-amber-400">{w.amount} ball</p>
                            </div>

                            {w.status === 'pending' && (
                              <div className="flex gap-2 pt-1 border-t border-slate-900">
                                <button
                                  onClick={() => handleAdminWithdraw(w.id, 'approved', w.tg_id, w.amount)}
                                  className="bg-emerald-600/10 hover:bg-emerald-600 border border-emerald-500/20 hover:border-emerald-500 text-emerald-400 hover:text-white transition font-bold py-1 px-3 rounded-lg text-[10px] flex-1"
                                >
                                  Tasdiqlash (Approve)
                                </button>
                                <button
                                  onClick={() => handleAdminWithdraw(w.id, 'rejected', w.tg_id, w.amount)}
                                  className="bg-rose-600/10 hover:bg-rose-600 border border-rose-500/20 hover:border-rose-500 text-rose-400 hover:text-white transition font-bold py-1 px-3 rounded-lg text-[10px] flex-1"
                                >
                                  Rad Etish (Reject)
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

              </div>
            )}
          </>
        )}
      </main>

      {/* Footer Navigation Bar */}
      <footer className="fixed bottom-0 left-0 right-0 max-w-md mx-auto bg-slate-900/60 backdrop-blur-xl border-t border-slate-900 px-6 py-2.5 flex justify-between items-center shadow-2xl z-40 rounded-t-3xl">
        <button 
          onClick={() => setActiveTab('home')} 
          className={`flex flex-col items-center gap-1 transition ${activeTab === 'home' ? 'text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <User size={18} className={activeTab === 'home' ? 'scale-110 transition' : ''} />
          <span className="text-[10px] font-semibold">Profil</span>
        </button>
        
        <button 
          onClick={() => setActiveTab('bonus')} 
          className={`flex flex-col items-center gap-1 transition ${activeTab === 'bonus' ? 'text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Gift size={18} className={activeTab === 'bonus' ? 'scale-110 transition' : ''} />
          <span className="text-[10px] font-semibold">Bonus</span>
        </button>

        <button 
          onClick={() => setActiveTab('leaderboard')} 
          className={`flex flex-col items-center gap-1 transition ${activeTab === 'leaderboard' ? 'text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Trophy size={18} className={activeTab === 'leaderboard' ? 'scale-110 transition' : ''} />
          <span className="text-[10px] font-semibold">Reyting</span>
        </button>

        <button 
          onClick={() => setActiveTab('wallet')} 
          className={`flex flex-col items-center gap-1 transition ${activeTab === 'wallet' ? 'text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Wallet size={18} className={activeTab === 'wallet' ? 'scale-110 transition' : ''} />
          <span className="text-[10px] font-semibold">Hamyon</span>
        </button>

        {isAdmin() && (
          <button 
            onClick={() => setActiveTab('admin')} 
            className={`flex flex-col items-center gap-1 transition ${activeTab === 'admin' ? 'text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <Settings size={18} className={activeTab === 'admin' ? 'scale-110 transition' : ''} />
            <span className="text-[10px] font-semibold">Admin</span>
          </button>
        )}
      </footer>
      
    </div>
  );
}
