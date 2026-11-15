// main.js
// -----------------------------------------------------------------------
// GHI CHÚ: File này là bản nháp tạm thời (TV3 viết hộ vì TV1 chưa làm), và
// HIỆN KHÔNG được <script> trong index.html gọi tới (xem comment trong
// index.html). Toàn bộ 4 KPI của dashboard hiện tại (Total Trips, Average
// Trip Duration, Peak Hour, Busiest Day) đã được temporal_charts.js tự tính
// theo đúng bộ lọc tháng đang chọn. Giữ file này lại làm tham khảo cho TV1
// khi bạn ấy xây index.html/main.js chính thức cho cả nhóm.
// -----------------------------------------------------------------------

d3.csv("../data/processed/summary/daily.csv").then(function(data) {

    // 1. Tính Total Trips
    const totalTrips = d3.sum(data, d => +d.trips);

    // 2. Tính Avg Duration (trung bình có trọng số theo số trips)
    let totalDurationWeight = 0;
    data.forEach(d => {
        totalDurationWeight += (+d.trips) * (+d.avg_duration_min);
    });
    const avgDuration = totalTrips > 0 ? totalDurationWeight / totalTrips : 0;

    // 3. Tính Member Share
    const memberTrips = d3.sum(data.filter(d => d.member_type === 'member'), d => +d.trips);
    const memberShare = totalTrips > 0 ? (memberTrips / totalTrips) * 100 : 0;

    // setText chỉ gán giá trị nếu phần tử thực sự tồn tại trên trang, tránh
    // lỗi "Cannot set properties of null" khi layout chưa có id tương ứng.
    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.innerText = value;
    }

    setText("kpi-total-trips", d3.format(",")(totalTrips));
    setText("kpi-avg-duration", avgDuration.toFixed(1) + " min");
    setText("kpi-member-share", memberShare.toFixed(1) + "%");

}).catch(error => console.error("Error loading KPI data:", error));