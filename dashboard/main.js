// main.js - Xử lý logic chung và KPI

// Hàm tính toán và hiển thị KPI
d3.csv("../data/processed/summary/daily.csv").then(function(data) {
    
    // 1. Tính Total Trips
    const totalTrips = d3.sum(data, d => +d.trips);
    
    // 2. Tính Avg Duration (Tính trung bình có trọng số dựa trên số trips)
    // Công thức: Tổng (trips * avg_duration) / Tổng trips
    let totalDurationWeight = 0;
    data.forEach(d => {
        totalDurationWeight += (+d.trips) * (+d.avg_duration_min);
    });
    const avgDuration = totalDurationWeight / totalTrips;
    
    // 3. Tính Member Share
    const memberData = data.filter(d => d.member_type === 'member');
    const memberTrips = d3.sum(memberData, d => +d.trips);
    const memberShare = (memberTrips / totalTrips) * 100;

    // Cập nhật DOM
    document.getElementById("kpi-total-trips").innerText = d3.format(",")(totalTrips);
    document.getElementById("kpi-avg-duration").innerText = avgDuration.toFixed(1) + " min";
    document.getElementById("kpi-member-share").innerText = memberShare.toFixed(1) + "%";

}).catch(error => console.error("Error loading KPI data:", error));