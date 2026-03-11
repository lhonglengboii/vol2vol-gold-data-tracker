# 📈 Vol2Vol Gold Data Tracker

An interactive web application built with Streamlit to visualize Intraday Volume and Open Interest (OI) data for Gold options/futures. 

🌐 **Live Website (เข้าใช้งานได้ที่นี่):** [https://xau888.streamlit.app](https://xau888.streamlit.app)

🙏 **Special Acknowledgments / ขอขอบคุณเป็นพิเศษ:**  
ขอขอบคุณ **คุณ @Fz** เจ้าของข้อมูลที่กรุณาให้ยืม Data มาใช้งานในโปรเจกต์นี้ครับ สามารถติดตามแหล่งที่มาของข้อมูลได้ที่: [https://github.com/pageth/Vol2VolData](https://github.com/pageth/Vol2VolData)

---

## ✨ Features (จุดเด่นของโปรเจกต์)

- **Interactive Charts:** แสดงกราฟแท่งเปรียบเทียบ Call/Put Volume และ Total Volume พร้อมเส้น Volatility Settle (Vol Settle) 
- **Timeline Animation:** มีระบบ Timeline Slider และปุ่ม Play/Pause เพื่อดูการเปลี่ยนแปลงของ Volume ในแต่ละช่วงเวลาของวัน (รองรับการกดคีย์บอร์ด ซ้าย/ขวา เพื่อเลื่อนเวลาต่อเนื่องเมื่อกด Pause)
- **Concurrent Data Fetching:** ดึงข้อมูลประวัติการแก้ไขไฟล์จาก GitHub เร็วขึ้นด้วย Multi-threading (`concurrent.futures`)
- **Data Tables:** ตารางแสดงข้อมูลดิบพร้อมแถบ Progress Bar เพื่อให้เห็นภาพรวมของ Volume ในแต่ละ Strike Price ได้ง่ายขึ้น
- **Two Main Views:** แบ่งหน้าจอการดูข้อมูลออกเป็น 2 แท็บหลักคือ **Intraday Volume** และ **Open Interest (OI)**

---

## 🛠️ How it Works (ระบบทำงานอย่างไร)

1. **Data Source:** ตัวแอปพลิเคชันจะเชื่อมต่อไปยัง GitHub API ของ Repository `pageth/Vol2VolData` เพื่อดึงประวัติการ Commit ในรอบวันของไฟล์ `IntradayData.txt` และ `OIData.txt`
2. **Data Parsing:** ข้อมูล text ที่ดึงมาจะถูกแปลงเป็น Pandas DataFrame โดยมีการดึงค่า Header และคำนวณหาค่า ATM (At-The-Money) อัตโนมัติ
3. **Visualization:** ใช้ไลบรารี `Plotly` ในการวาดกราฟแบบ Interactive ทำให้ผู้ใช้สามารถนำเมาส์ไปชี้เพื่อดูรายละเอียดในแต่ละจุดได้
4. **State Management:** ใช้ `st.session_state` ของ Streamlit ควบคุมการเล่น Animation และการทำ Auto-Focus ร่วมกับแทรกสคริปต์ JavaScript เพื่อความลื่นไหลของ UI

---

## 💡 How to Use (วิธีการใช้งาน)

1. **เปิดเว็บไซต์:** เข้าไปที่ [https://xau888.streamlit.app](https://xau888.streamlit.app)
2. **โหมดแสดงกราฟ (มุมขวาบน):** สามารถเลือกสลับมุมมองกราฟได้ระหว่างการแยก `Call / Put Vol` หรือดูรวมเป็น `Total Vol`
3. **ปุ่ม Refresh Data:** ใช้เพื่อดึงข้อมูลอัปเดตล่าสุด ณ เวลานั้น (ข้อมูลของวันปัจจุบันจะเริ่มเข้ามาตั้งแต่เวลา 12:30 น. เป็นต้นไป)
4. **Timeline Slider (หน้า Intraday):** 
   - เลื่อนแถบ Slider เพื่อดูข้อมูล ณ เวลาต่างๆ 
   - กดปุ่ม **Play** เพื่อให้ระบบเล่นภาพเคลื่อนไหวแบบอัตโนมัติ
   - เมื่อกด **Pause** ระบบจะดึง Focus ไปที่ปุ่ม Slider ให้อัตโนมัติ คุณสามารถใช้ปุ่มลูกศร ⬅️ ซ้าย / ขวา ➡️ บนคีย์บอร์ดเพื่อเลื่อนดูทีละเฟรมได้ทันที
5. **Data Tables:** ตารางด้านล่างกราฟสามารถคลิกที่หัวตารางเพื่อเรียงลำดับข้อมูล (Sort) ตามคอลัมน์ที่ต้องการได้

---
*Built with ❤️ using [Streamlit](https://streamlit.io/)*
