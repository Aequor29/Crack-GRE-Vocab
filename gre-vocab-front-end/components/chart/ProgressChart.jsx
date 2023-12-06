import { Doughnut } from "react-chartjs-2";
import Chart from "chart.js/auto";

const ProgressChart = ({ progress }) => {
  const data = {
    labels: ["Learned Words", "Remaining Words", "Well Remembered Words"],
    datasets: [
      {
        label: "# of Words",
        data: [
          progress.learned_words_count,
          progress.total_words_count - progress.learned_words_count,
          progress.well_remembered_words_count,
        ],
        backgroundColor: [
          "rgba(54, 162, 235, 0.6)",
          "rgba(255, 206, 86, 0.6)",
          "rgba(75, 192, 192, 0.6)",
        ],
        borderColor: [
          "rgba(54, 162, 235, 1)",
          "rgba(255, 206, 86, 1)",
          "rgba(75, 192, 192, 1)",
        ],
        borderWidth: 1,
      },
    ],
  };

  return <Doughnut data={data} />;
};

export default ProgressChart;
