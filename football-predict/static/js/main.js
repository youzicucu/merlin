document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('predictForm');
    const homeTeamInput = document.getElementById('home_team');
    const awayTeamInput = document.getElementById('away_team');
    const homeSuggestions = document.getElementById('home_suggestions');
    const awaySuggestions = document.getElementById('away_suggestions');
    const resultDiv = document.getElementById('result');
    const predictBtn = document.getElementById('predictBtn');
    
    // 预测结果映射
    const predictionMap = {
        'win': ['🏆 主队获胜', '#2ecc71'],
        'draw': ['🤝 双方战平', '#f1c40f'],
        'loss': ['🏆 客队获胜', '#e74c3c']
    };
    
    // 处理表单提交
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const homeTeam = homeTeamInput.value.trim();
        const awayTeam = awayTeamInput.value.trim();
        
        resultDiv.style.display = 'none';
        
        if (!homeTeam || !awayTeam) {
            showResult({
                title: '❌ 请填写双方球队名称',
                details: ''
            }, 'error');
            return;
        }
        
        // 同一球队不能对战自己
        if (homeTeam.toLowerCase() === awayTeam.toLowerCase()) {
            showResult({
                title: '❌ 主队和客队不能是同一支球队',
                details: ''
            }, 'error');
            return;
        }
        
        try {
            // 禁用提交按钮并显示加载状态
            predictBtn.disabled = true;
            predictBtn.innerHTML = '<span class="spinner"></span> 数据分析中...';
            
            // 发送预测请求
            const response = await fetch('/api/predict/teams', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    home_team: homeTeam,
                    away_team: awayTeam
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || '预测失败');
            }
            
            const prediction = data.prediction;
            const features = data.features;
            
            // 准备详细信息显示
            const details = `
                <ul class="stats-list">
                    <li>
                        <strong>${features.home_team}</strong>
                        <div>场均进球：${features.home_avg_goals}</div>
                        <div>近期胜率：${(features.home_win_rate * 100).toFixed(1)}%</div>
                    </li>
                    <li>
                        <strong>${features.away_team}</strong>
                        <div>场均进球：${features.away_avg_goals}</div>
                        <div>近期胜率：${(features.away_win_rate * 100).toFixed(1)}%</div>
                    </li>
                </ul>
            `;
            
            // 显示预测结果
            showResult({
                title: predictionMap[prediction]?.[0] || '未知结果',
                details: details
            }, prediction);
            
        } catch (error) {
            console.error('预测请求错误:', error);
            showResult({
                title: `❌ ${error.message}`,
                details: '请检查球队名称是否正确，或稍后重试'
            }, 'error');
        } finally {
            // 恢复提交按钮
            predictBtn.disabled = false;
            predictBtn.textContent = '开始智能分析';
        }
    });
    
    // 显示预测结果
    function showResult(content, status = 'success') {
        resultDiv.innerHTML = `
            <div class="prediction-result" style="color: ${predictionMap[status]?.[1] || '#2c3e50'}">
                ${content.title}
            </div>
            <div class="stats-box">
                ${content.details}
            </div>
        `;
        resultDiv.className = status;
        resultDiv.style.display = 'block';
        
        // 滚动到结果区域
        resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    // 球队搜索建议功能
    function setupTeamSuggestions(inputElement, suggestionsElement) {
        let debounceTimer;
        
        inputElement.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const query = this.value.trim();
            
            if (query.length < 2) {
                suggestionsElement.style.display = 'none';
                return;
            }
            
            // 添加延迟避免频繁请求
            debounceTimer = setTimeout(async () => {
                try {
                    const response = await fetch(`/api/teams/search?q=${encodeURIComponent(query)}`);
                    const data = await response.json();
                    
                    if (data.teams && data.teams.length > 0) {
                        renderSuggestions(data.teams, suggestionsElement, inputElement);
                    } else {
                        suggestionsElement.style.display = 'none';
                    }
                } catch (error) {
                    console.error('获取球队建议失败:', error);
                }
            }, 300);
        });
        
        // 点击其他区域关闭建议
        document.addEventListener('click', function(e) {
            if (e.target !== inputElement && !suggestionsElement.contains(e.target)) {
                suggestionsElement.style.display = 'none';
            }
        });
    }
    
    // 渲染球队建议列表
    function renderSuggestions(teams, container, inputElement) {
        container.innerHTML = '';
        
        teams.forEach(team => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            
            const displayName = team.zh_name || team.name;
            const secondaryName = team.zh_name ? team.name : '';
            
            item.innerHTML = `
                <div class="team-name">${displayName}</div>
                ${secondaryName ? `<div class="team-info">${secondaryName} · ${team.country || ''}</div>` : ''}
            `;
            
            item.addEventListener('click', function() {
                inputElement.value = displayName;
                container.style.display = 'none';
            });
            
            container.appendChild(item);
        });
        
        container.style.display = 'block';
    }
    
    // 设置球队搜索建议
    setupTeamSuggestions(homeTeamInput, homeSuggestions);
    setupTeamSuggestions(awayTeamInput, awaySuggestions);
});
