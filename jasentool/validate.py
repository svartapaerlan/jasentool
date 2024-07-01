"""Module for validating pipelines"""

import json
from jasentool.database import Database
from jasentool.utils import Utils

class Validate:
    """Class to validate old pipeline (cgviz) with new pipeline (jasen)"""
    def get_sample_id(self, results):
        """Get sample ID from mongodb"""
        return results["run_metadata"]["run"]["sample_name"]

    def get_species_name(self, results):
        """Get species name from mongodb"""
        return results["species_prediction"][0]["scientific_name"]

    def _check_exists(self, db_collection, sample_id):
        """Check if sample ID exists in mongodb"""
        return bool(list(Database.find(db_collection, {"id": sample_id}, {})))

    def search(self, search_query, search_kw, search_list):
        """Search for query in list of arrays"""
        return [element for element in search_list if element[search_kw] == search_query]

    def get_virulence_results(self, results):
        """Get virulence results"""
        return self.search("VIRULENCE", "type", results["element_type_result"])

    def get_pvl(self, results):
        """Get pvl result"""
        virulence_results = self.get_virulence_results(results)
        return bool(self.search("lukS-PV", "gene_symbol", virulence_results[0]["result"]["genes"]))

    def get_mlst(self, results):
        """Get mlst result"""
        return self.search("mlst", "type", results["typing_result"])

    def get_cgmlst(self, results):
        """Get cgmlst result"""
        return self.search("cgmlst", "type", results["typing_result"])

    def get_mdb_cgv_data(self, db_collection, sample_id):
        """Get sample mongodb data"""
        mdb_pvl = list(Database.get_pvl(db_collection, {"id": sample_id, "metadata.QC": "OK"}))
        mdb_mlst = list(Database.get_mlst(db_collection, {"id": sample_id, "metadata.QC": "OK"}))
        mdb_cgmlst = list(Database.get_cgmlst(db_collection, {"id": sample_id, "metadata.QC": "OK"}))
        try:
            mdb_pvl_present = int(mdb_pvl[0]["aribavir"]["lukS_PV"]["present"])
            mdb_mlst_seqtype = str(mdb_mlst[0]["mlst"]["sequence_type"]) if mdb_mlst[0]["mlst"]["sequence_type"] != "-" else str(None)
            mdb_mlst_alleles = mdb_mlst[0]["mlst"]["alleles"]
            mdb_cgmlst_alleles = mdb_cgmlst[0]["alleles"]
            return {"pvl": mdb_pvl_present, "mlst_seqtype": mdb_mlst_seqtype,
                    "mlst_alleles": mdb_mlst_alleles, "cgmlst_alleles": mdb_cgmlst_alleles}
        except IndexError:
            return False

    def get_fin_data(self, sample_json):
        """Get sample input file data"""
        fin_pvl_present = self.get_pvl(sample_json)
        fin_mlst = self.get_mlst(sample_json)
        fin_cgmlst = self.get_cgmlst(sample_json)
        fin_mlst_seqtype = str(fin_mlst[0]["result"]["sequence_type"])
        fin_mlst_alleles = fin_mlst[0]["result"]["alleles"]
        fin_cgmlst_alleles = list(fin_cgmlst[0]["result"]["alleles"].values())
        return {"pvl": fin_pvl_present, "mlst_seqtype": fin_mlst_seqtype,
                "mlst_alleles": fin_mlst_alleles, "cgmlst_alleles": fin_cgmlst_alleles}

    def compare_mlst_alleles(self, old_mlst_alleles, new_mlst_alleles):
        """Parse through mlst alleles of old and new pipeline and compare results"""
        match_count, total_count = 0, 0
        for allele in old_mlst_alleles:
            if str(old_mlst_alleles[allele]) == str(new_mlst_alleles[allele]):
                match_count += 1
            total_count += 1
        return 100*(match_count/total_count)

    def compare_cgmlst_alleles(self, old_cgmlst_alleles, new_cgmlst_alleles):
        """Parse through cgmlst alleles of old and new pipeline and compare results"""
        match_count, total_count = 0, 0
        for idx, old_allele in enumerate(old_cgmlst_alleles):
            if str(old_allele) == str(new_cgmlst_alleles[idx]):
                match_count += 1
            total_count += 1
        return 100*(match_count/total_count)

    def compare_data(self, sample_id, old_data, new_data):
        """Compare data between old pipeline and new pipeline"""
        pvl_comp = int(old_data["pvl"] == new_data["pvl"])
        mlst_seqtype_comp = int(old_data["mlst_seqtype"] == new_data["mlst_seqtype"])
        if mlst_seqtype_comp == 0:
            mlst_at_list = [f'{old_data["mlst_alleles"][gene]},{new_data["mlst_alleles"][gene]}'
                            for gene in sorted(old_data["mlst_alleles"].keys())]
            mlst_at_str = ",".join(mlst_at_list)
            return False, f'{sample_id},{old_data["mlst_seqtype"]},{new_data["mlst_seqtype"]},{mlst_at_str}'
        mlst_alleles = self.compare_mlst_alleles(old_data["mlst_alleles"], new_data["mlst_alleles"])
        cgmlst_alleles = self.compare_cgmlst_alleles(old_data["cgmlst_alleles"], new_data["cgmlst_alleles"])
        return True, f"{sample_id},{pvl_comp},{mlst_seqtype_comp},{mlst_alleles},{cgmlst_alleles}"

    def run(self, input_files, output_fpaths, db_collection, combined_output):
        """Execute validation of new pipeline (jasen)"""
        utils = Utils()
        csv_output = "sample_id,pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"
        mlst_at_header = "old_arcC,new_arcC,old_aroE,new_aroE,old_glpF,new_glpF,old_gmk,new_gmk,old_pta,new_pta,old_tpi,new_tpi,old_yqiL,new_yqiL"
        failed_csv_output = f"sample_id,old_mlst_seqtype,new_mlst_allele_matches(%),{mlst_at_header}"
        for input_idx, input_file in enumerate(input_files):
            with open(input_file, 'r', encoding="utf-8") as fin:
                sample_json = json.load(fin)
                sample_id = self.get_sample_id(sample_json)
                if not self._check_exists(db_collection, sample_id):
                    print(f"The sample provided ({sample_id}) does not exist in the provided database ({Database.db_name}) or collection ({db_collection}).")
                    continue
                mdb_data_dict = self.get_mdb_cgv_data(db_collection, sample_id)
                if mdb_data_dict:
                    #species_name = self.get_species_name(sample_json)
                    fin_data_dict = self.get_fin_data(sample_json)
                    passed_val, compared_data_output = self.compare_data(sample_id, mdb_data_dict, fin_data_dict)
                    if passed_val:
                        csv_output += "\n" + compared_data_output
                    else:
                        failed_csv_output += "\n" + compared_data_output
            if not combined_output:
                utils.write_out_txt(csv_output, f"{output_fpaths[input_idx]}.csv")
                utils.write_out_txt(failed_csv_output, f"{output_fpaths[input_idx]}_failed.csv")
                csv_output = "pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"
                failed_csv_output = "pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"

        if combined_output:
            utils.write_out_txt(csv_output, f"{output_fpaths[0]}.csv")
            utils.write_out_txt(failed_csv_output, f"{output_fpaths[0]}_failed.csv")
